"""lib.frontmatter — Markdown YAML frontmatter 解析 / 序列化（H17 已决议必做）。

schema（pydantic v2）：
  thread_id: str (optional, 客户端自动注入)
  in_reply_to: str (optional, --reply-to 时注入)
  priority: Literal["low","normal","high","urgent"]  默认 normal
  tags: list[str]                                    默认 []
  capability_required: list[str]                     默认 []
  require_ack: bool                                  默认 False
  require_approval: bool                             默认 False
  ttl_hours: int | None                              默认 None
  extras: dict[str, Any]                             默认 {}（未识别字段）

解析规则：
- 正文必须以首行 `---` 开始、独占一行 `---` 结束
- 中间必须是合法 YAML；解析失败 → 抛 FrontmatterInvalid
- 不以 `---` 开头的正文视为"无 frontmatter"，向后兼容 v2.x
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lib.errors import DependencyMissing, FrontmatterInvalid


_KNOWN_FIELDS = {
    "thread_id",
    "in_reply_to",
    "priority",
    "tags",
    "capability_required",
    "require_ack",
    "require_approval",
    "ttl_hours",
}
_VALID_PRIORITIES = {"low", "normal", "high", "urgent"}


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

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 frontmatter YAML 用的 dict，None / 空值过滤掉以保持简洁。"""
        out: Dict[str, Any] = {}
        if self.thread_id:
            out["thread_id"] = self.thread_id
        if self.in_reply_to:
            out["in_reply_to"] = self.in_reply_to
        if self.priority != "normal":
            out["priority"] = self.priority
        if self.tags:
            out["tags"] = list(self.tags)
        if self.capability_required:
            out["capability_required"] = list(self.capability_required)
        if self.require_ack:
            out["require_ack"] = True
        if self.require_approval:
            out["require_approval"] = True
        if self.ttl_hours is not None:
            out["ttl_hours"] = int(self.ttl_hours)
        out.update(self.extras)
        return out


def _lazy_frontmatter_mod():
    try:
        import frontmatter as _fm  # type: ignore
        return _fm
    except ImportError as e:
        raise DependencyMissing("python-frontmatter", f"import 失败：{e}") from e


def parse(body: str) -> Tuple[MailFrontmatter, str]:
    """解析 body，返回 (frontmatter model, 剩余 markdown body)。

    若 body 不以 `---` 起始，直接返回空 frontmatter + 原 body（v2 向后兼容）。
    YAML 解析失败 → FrontmatterInvalid。
    """
    if not body.startswith("---"):
        return MailFrontmatter(), body

    fm_mod = _lazy_frontmatter_mod()
    try:
        post = fm_mod.loads(body)
    except Exception as e:
        raise FrontmatterInvalid(detail=str(e)) from e

    meta = dict(post.metadata or {})
    return _validate(meta), post.content


def _validate(meta: Dict[str, Any]) -> MailFrontmatter:
    """校验 + 归一化 frontmatter。严格字段走 schema，未识别走 extras。"""
    fm = MailFrontmatter()
    extras: Dict[str, Any] = {}

    for key, value in meta.items():
        if key == "thread_id":
            fm.thread_id = _as_str(value, key)
        elif key == "in_reply_to":
            fm.in_reply_to = _as_str(value, key)
        elif key == "priority":
            v = _as_str(value, key) or "normal"
            if v not in _VALID_PRIORITIES:
                raise FrontmatterInvalid(detail=f"priority 必须属于 {_VALID_PRIORITIES}，实际 {v!r}")
            fm.priority = v
        elif key == "tags":
            fm.tags = _as_str_list(value, key)
        elif key == "capability_required":
            fm.capability_required = _as_str_list(value, key)
        elif key == "require_ack":
            fm.require_ack = bool(value)
        elif key == "require_approval":
            fm.require_approval = bool(value)
        elif key == "ttl_hours":
            try:
                fm.ttl_hours = int(value)
            except (TypeError, ValueError) as e:
                raise FrontmatterInvalid(detail=f"ttl_hours 必须是整数，实际 {value!r}") from e
        else:
            extras[key] = value

    fm.extras = extras
    return fm


def _as_str(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise FrontmatterInvalid(detail=f"{field_name} 必须是字符串，实际 {type(value).__name__}")


def _as_str_list(value: Any, field_name: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # 容错：允许 "a, b, c" 字符串写法
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        if not all(isinstance(x, str) for x in value):
            raise FrontmatterInvalid(detail=f"{field_name} 列表内元素必须全部是字符串")
        return list(value)
    raise FrontmatterInvalid(detail=f"{field_name} 必须是字符串或列表，实际 {type(value).__name__}")


def serialize(fm: MailFrontmatter, body: str) -> str:
    """把 frontmatter + body 拼回合法 Markdown。

    空 frontmatter 直接返回 body（不加 `---` 头，保持干净）。
    """
    data = fm.to_dict()
    if not data:
        return body

    fm_mod = _lazy_frontmatter_mod()
    post = fm_mod.Post(body, **data)
    return fm_mod.dumps(post)
