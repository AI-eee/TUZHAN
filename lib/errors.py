"""lib.errors — 结构化异常 + 错误码表。

设计约束：
- 所有面向用户的错误必须是 MailError 子类
- 每个错误码都应在 SKILL.md §4 故障速查表里有条目
- exit code 按 Unix 风格：2=usage, 64=data error, 70=software, 74=io, 75=temp fail, 78=config

P0-2 负责完善错误码与字段；skeleton 阶段先占位最常用的几类。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class MailError(Exception):
    """所有 mail 命令抛出的结构化错误基类。

    code: 机读错误码（snake_case，错误码表的 key）
    message: 人读错误描述
    hint: 下一步建议（AI Agent 可据此自愈）
    context: 附加字段（如 msg_id / account / retry_after）
    exit_code: POSIX exit code
    """
    code: str = "unknown"
    message: str = ""
    hint: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    exit_code: int = 70

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "context": self.context,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# —— 常用错误工厂 ——

class NotImplementedYet(MailError):
    def __init__(self, command: str, hint: str = ""):
        super().__init__(
            code="not_implemented_yet",
            message=f"命令 `{command}` 在当前版本尚未实现",
            hint=hint or "参考 PRD-0054 排期，等待后续 P0 批次上线",
            context={"command": command},
            exit_code=69,  # EX_UNAVAILABLE
        )


class NoApiKey(MailError):
    def __init__(self):
        super().__init__(
            code="no_api_key",
            message="未检测到 TUZHAN_API_KEY",
            hint="export TUZHAN_API_KEY=... 或编辑 data/config.toml",
            exit_code=78,  # EX_CONFIG
        )


class ConnectivityFail(MailError):
    def __init__(self, url: str, reason: str = ""):
        super().__init__(
            code="connectivity_fail",
            message=f"连接服务端失败：{url}",
            hint=reason or "检查网络代理与 TUZHAN_API_BASE 设置",
            context={"url": url, "reason": reason},
            exit_code=75,  # EX_TEMPFAIL
        )


class FrontmatterInvalid(MailError):
    def __init__(self, detail: str):
        super().__init__(
            code="frontmatter_invalid",
            message="Markdown frontmatter 语法错误",
            hint="首行与关闭行必须是 `---`，之间是合法 YAML；不确定就不写 frontmatter",
            context={"detail": detail},
            exit_code=65,  # EX_DATAERR
        )


class RateLimited(MailError):
    def __init__(self, retry_after: Optional[int] = None):
        super().__init__(
            code="rate_limited",
            message="触发服务端限流",
            hint=f"约 {retry_after}s 后重试" if retry_after else "降低调用频率后重试",
            context={"retry_after": retry_after} if retry_after else {},
            exit_code=75,
        )


class CircuitOpen(MailError):
    def __init__(self, account: str = ""):
        super().__init__(
            code="circuit_open",
            message="账户被服务端熔断",
            hint="请管理员在 SEE2AI Dashboard 手动解锁；客户端不应自动重试",
            context={"account": account} if account else {},
            exit_code=75,
        )


class AuthFail(MailError):
    def __init__(self, status: int = 401):
        super().__init__(
            code="auth_fail",
            message=f"服务端认证失败（HTTP {status}）",
            hint="检查 TUZHAN_API_KEY 是否正确、是否过期、账号是否被管理员禁用",
            context={"status": status},
            exit_code=77,  # EX_NOPERM
        )


class DependencyMissing(MailError):
    def __init__(self, pkg: str, hint: str = ""):
        super().__init__(
            code="dependency_missing",
            message=f"缺少依赖：{pkg}",
            hint=hint or f"运行 pip install --user -r requirements.txt，或单独 pip install --user {pkg}",
            context={"package": pkg},
            exit_code=69,  # EX_UNAVAILABLE
        )


class SchemaViolation(MailError):
    def __init__(self, detail: str, field_path: str = ""):
        super().__init__(
            code="schema_violation",
            message=f"响应 schema 校验失败：{detail}",
            hint="可能服务端版本不兼容，请 bin/mail version 对比版本并升级",
            context={"detail": detail, "field_path": field_path},
            exit_code=65,
        )


class ChecksumFail(MailError):
    def __init__(self, expected: str, actual: str):
        super().__init__(
            code="checksum_fail",
            message="SHA256 校验失败，可能下载被篡改或损坏",
            hint="删除 data/cache/staging/ 后重试；如持续失败请核对 CDN 与 manifest 一致性",
            context={"expected": expected, "actual": actual},
            exit_code=65,
        )


class NoMatch(MailError):
    def __init__(self, query: str, candidates: Optional[list] = None):
        super().__init__(
            code="no_match",
            message=f"无法在花名册中定位 `{query}`",
            hint="先跑 bin/mail list 拉取最新花名册；或用 emp_id 精确指定",
            context={"query": query, "candidates": candidates or []},
            exit_code=65,
        )


class ApiErrorFromServer(MailError):
    """服务端信封返回 {ok: false, code, message, hint} 时，客户端封装。

    与 RateLimited / CircuitOpen / AuthFail 等 HTTP 状态码映射的错误不同，
    ApiErrorFromServer 用于承载服务端自定义业务错误码（如 frontmatter_invalid、
    thread_not_found、capability_required 等）。
    """

    def __init__(self, code: str, message: str, hint: str = "", context: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=code,
            message=message,
            hint=hint,
            context=context or {},
            exit_code=65,
        )
