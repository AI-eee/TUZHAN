"""lib.frontmatter — Markdown YAML frontmatter 解析 / 序列化（H17 已决议必做）。

字段 schema（pydantic v2，P0-2 实现）：
  thread_id: str (optional, 客户端自动注入)
  in_reply_to: str (optional, --reply-to 时注入)
  priority: Literal["low","normal","high","urgent"]
  tags: list[str]
  capability_required: list[str]
  require_ack: bool
  require_approval: bool
  ttl_hours: int

解析规则：
- 正文必须以首行 `---` 开始、独占一行 `---` 结束
- 中间必须是合法 YAML；解析失败 → 抛 FrontmatterInvalid
- 不以 `---` 开头的正文视为"无 frontmatter"，向后兼容 v2.x
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MailFrontmatter:
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    priority: str = "normal"
    tags: List[str] = field(default_factory=list)
    capability_required: List[str] = field(default_factory=list)
    require_ack: bool = False
    require_approval: bool = False
    ttl_hours: Optional[int] = None
    extras: Dict[str, Any] = field(default_factory=dict)


def parse(body: str) -> Tuple[MailFrontmatter, str]:
    """解析 body，返回 (frontmatter, 剩余 markdown body)。

    P0-2 实现：用 python-frontmatter。skeleton 阶段抛 NotImplementedError。
    """
    raise NotImplementedError("P0-2: 用 python-frontmatter + pydantic v2 实现")


def serialize(fm: MailFrontmatter, body: str) -> str:
    """把 frontmatter + body 拼回合法 Markdown。仅用于客户端注入 thread_id / in_reply_to。"""
    raise NotImplementedError("P0-2")
