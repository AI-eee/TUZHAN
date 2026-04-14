"""lib.api_client — 服务端 HTTP 客户端。

职责（P0-2 完整实现）：
- httpx.Client，基于 TUZHAN_API_BASE（env 优先 → data/config.toml 兜底）
- Bearer auth（TUZHAN_API_KEY）
- 重试 + 超时 + JSON schema 校验（pydantic v2）
- 限流感知（响应 429 → 抛 RateLimited）
- 熔断感知（响应 423 / 自定义 code → 抛 CircuitOpen）

skeleton 阶段仅保留类骨架 + 明确的 TODO 锚点，禁止悄悄半实现。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ApiConfig:
    base_url: str
    api_key: str
    timeout_s: float = 30.0
    max_retries: int = 3


class ApiClient:
    """TUZHAN 服务端 REST 客户端（v3.0 skeleton）"""

    def __init__(self, cfg: ApiConfig):
        self.cfg = cfg
        # TODO(P0-2): self._client = httpx.Client(base_url=cfg.base_url, timeout=cfg.timeout_s, headers={...})
        self._client = None

    def close(self) -> None:
        # TODO(P0-2): self._client.close()
        pass

    # —— 端点封装，P0-2 / P0-8 / P0-9 分批实现 ——

    def health(self) -> Dict[str, Any]:
        raise NotImplementedError("P0-2")

    def get_version(self) -> Dict[str, Any]:
        raise NotImplementedError("P0-2")

    def get_manifest(self, version: str) -> Dict[str, Any]:
        raise NotImplementedError("P0-2")

    def list_projects(self) -> Dict[str, Any]:
        raise NotImplementedError("P0-9")

    def receive_messages(self, since: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError("P0-9")

    def send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("P0-9")

    def ack_message(self, msg_id: str, state: str, note: str = "") -> Dict[str, Any]:
        raise NotImplementedError("P0-9")

    def trace_message(self, msg_id: str) -> Dict[str, Any]:
        raise NotImplementedError("P0-9")

    def profile_set(self, capabilities: list) -> Dict[str, Any]:
        raise NotImplementedError("P0-9")

    def directory_query(self, capability: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError("P0-9")
