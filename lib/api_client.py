"""lib.api_client — 服务端 HTTP 客户端（P0-2 真实实现）。

职责：
- httpx.Client，base_url = TUZHAN_API_BASE（env 优先 → data/config.toml 兜底）
- Bearer auth（TUZHAN_API_KEY）
- 指数退避重试（5xx / 网络错 / 429）
- 超时 + 限流（429 + Retry-After）→ 抛 RateLimited
- 熔断（423 / code=circuit_open）→ 抛 CircuitOpen
- 认证失败（401/403）→ 抛 AuthFail
- 响应信封校验：success -> {ok: true, data: ...}；error -> {ok: false, code, message, hint}

其他端点封装薄：每个 method 一行 self._request + 返回 data 字段。
业务 schema 校验由调用方（send/sync/...）按需做，本类只保证传输层正确。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from lib.errors import (
    ApiErrorFromServer,
    AuthFail,
    CircuitOpen,
    ConnectivityFail,
    DependencyMissing,
    NoApiKey,
    RateLimited,
    SchemaViolation,
)


DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5  # 秒；重试延迟 = base * 2^attempt


@dataclass
class ApiConfig:
    base_url: str
    api_key: str
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_retries: int = DEFAULT_MAX_RETRIES

    @classmethod
    def from_env(cls) -> "ApiConfig":
        """优先 env，再 fallback 到 data/config.toml（由 init.py 生成）。"""
        api_key = os.environ.get("TUZHAN_API_KEY", "").strip()
        base_url = os.environ.get("TUZHAN_API_BASE", "").strip()

        if not api_key or not base_url:
            # 尝试从 config.toml 补齐（只有有 key/base_url 缺失才读）
            cfg_key, cfg_base = _read_config_toml()
            api_key = api_key or cfg_key
            base_url = base_url or cfg_base

        if not api_key:
            raise NoApiKey()
        if not base_url:
            raise ConnectivityFail(url="<未配置>", reason="缺少 TUZHAN_API_BASE，请 export 或写 data/config.toml")

        return cls(base_url=base_url.rstrip("/"), api_key=api_key)


def _read_config_toml() -> tuple[str, str]:
    """从 data/config.toml 读 api_key / api_base。缺失时返回空串。"""
    try:
        from lib import paths

        cfg_file = paths.config_toml()
        if not cfg_file.exists():
            return "", ""

        try:
            import tomllib  # type: ignore[attr-defined]

            with cfg_file.open("rb") as f:
                data = tomllib.load(f)
        except ImportError:
            try:
                import tomli  # type: ignore
            except ImportError as e:
                raise DependencyMissing("tomli", f"Python <3.11 需要 tomli：{e}") from e
            with cfg_file.open("rb") as f:
                data = tomli.load(f)

        auth = data.get("auth", {})
        return str(auth.get("api_key", "")), str(auth.get("api_base", ""))
    except DependencyMissing:
        raise
    except Exception:
        return "", ""


def _lazy_httpx():
    try:
        import httpx  # type: ignore
        return httpx
    except ImportError as e:
        raise DependencyMissing("httpx", f"import 失败：{e}") from e


class ApiClient:
    """TUZHAN 服务端 REST 客户端"""

    def __init__(self, cfg: Optional[ApiConfig] = None):
        self.cfg = cfg or ApiConfig.from_env()
        httpx = _lazy_httpx()
        self._client = httpx.Client(
            base_url=self.cfg.base_url,
            timeout=self.cfg.timeout_s,
            headers={
                "Authorization": f"Bearer {self.cfg.api_key}",
                "User-Agent": "tuzhan-agent-mail/v3.0.0-dev",
                "Accept": "application/json",
            },
        )

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None  # type: ignore

    # —— 核心请求 —— 所有端点走这里
    def _request(self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        httpx = _lazy_httpx()

        last_exc: Optional[Exception] = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = self._client.request(method, path, json=json_body, params=params)
            except httpx.NetworkError as e:
                last_exc = ConnectivityFail(url=f"{self.cfg.base_url}{path}", reason=str(e))
                self._maybe_sleep(attempt)
                continue
            except httpx.TimeoutException as e:
                last_exc = ConnectivityFail(url=f"{self.cfg.base_url}{path}", reason=f"timeout: {e}")
                self._maybe_sleep(attempt)
                continue

            # 状态码语义
            if resp.status_code in (401, 403):
                raise AuthFail(status=resp.status_code)
            if resp.status_code == 423:
                raise CircuitOpen()
            if resp.status_code == 429:
                retry_after = _parse_retry_after(resp)
                if attempt < self.cfg.max_retries:
                    time.sleep(retry_after or DEFAULT_BACKOFF_BASE * (2 ** attempt))
                    continue
                raise RateLimited(retry_after=retry_after)
            if 500 <= resp.status_code < 600:
                last_exc = ConnectivityFail(url=path, reason=f"server {resp.status_code}")
                self._maybe_sleep(attempt)
                continue

            # 2xx / 4xx(非上面处理的) 都走信封解析
            return self._parse_envelope(resp, path)

        assert last_exc is not None
        raise last_exc

    def _maybe_sleep(self, attempt: int) -> None:
        if attempt < self.cfg.max_retries:
            time.sleep(DEFAULT_BACKOFF_BASE * (2 ** attempt))

    def _parse_envelope(self, resp: Any, path: str) -> Dict[str, Any]:
        """期望服务端返回 {ok: true/false, data?, code?, message?, hint?, context?}"""
        try:
            body = resp.json()
        except Exception as e:
            raise SchemaViolation(detail=f"响应非合法 JSON ({path}): {e}") from e

        if not isinstance(body, dict):
            raise SchemaViolation(detail=f"响应必须是 JSON object，实际 {type(body).__name__} ({path})")

        if body.get("ok") is True:
            return body.get("data", {})

        # 业务错误：从信封抽取错误码
        raise ApiErrorFromServer(
            code=str(body.get("code", f"http_{resp.status_code}")),
            message=str(body.get("message", f"服务端返回 {resp.status_code}")),
            hint=str(body.get("hint", "")),
            context=dict(body.get("context", {})),
        )

    # —— 端点封装（P0-8 / P0-9 按需扩展）——

    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")

    def get_version(self) -> Dict[str, Any]:
        return self._request("GET", "/version")

    def get_manifest(self, version: str) -> Dict[str, Any]:
        return self._request("GET", f"/versions/{version}/manifest")

    def get_changelog(self) -> Dict[str, Any]:
        return self._request("GET", "/versions/changelog")

    def me(self) -> Dict[str, Any]:
        return self._request("GET", "/me")

    def list_projects(self) -> Dict[str, Any]:
        return self._request("GET", "/projects")

    def receive_messages(self, since: Optional[str] = None) -> Dict[str, Any]:
        params = {"since": since} if since else None
        return self._request("GET", "/messages/receive", params=params)

    def send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/messages/send", json_body=payload)

    def ack_message(self, msg_id: str, state: str, note: str = "") -> Dict[str, Any]:
        return self._request("POST", f"/messages/{msg_id}/ack",
                             json_body={"state": state, "note": note})

    def trace_message(self, msg_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/messages/{msg_id}/trace")

    def profile_set(self, capabilities: list) -> Dict[str, Any]:
        return self._request("POST", "/profile", json_body={"capabilities": capabilities})

    def directory_query(self, capability: Optional[str] = None) -> Dict[str, Any]:
        params = {"capability": capability} if capability else None
        return self._request("GET", "/directory", params=params)

    def request_approval(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/approve/request", json_body=payload)


def _parse_retry_after(resp: Any) -> Optional[int]:
    val = resp.headers.get("Retry-After")
    if not val:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
