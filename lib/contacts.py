"""lib.contacts — 花名册管理（P0-9 实现）。

职责：
- list_projects：GET /mail/api/projects → 写 data/contacts/roster.md
- resolve：传入昵称或 emp_id → 返回精确 emp_id 或候选列表（供 send 模糊匹配用）
- profile_set / directory_query：能力声明 + 查找（H13）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def list_and_write(as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")


def resolve(name_or_emp_id: str) -> Dict[str, Any]:
    """返回 {exact: Optional[str], candidates: List[Dict]}"""
    raise NotImplementedError("P0-9")


def profile_set(capabilities: List[str], as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")


def directory(capability: Optional[str] = None, as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")


def ack(msg_id: str, state: str, note: str = "", as_json: bool = False) -> Dict[str, Any]:
    """5 态回执推进（H18）。state ∈ {acknowledged, acted, completed}"""
    raise NotImplementedError("P0-9")


def trace(msg_id: str, as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")
