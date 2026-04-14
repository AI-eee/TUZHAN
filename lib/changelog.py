"""lib.changelog — changelog 拉取与展示（P0-9 实现）。

职责：
- GET /mail/api/versions/changelog → 缓存到 data/cache/changelog.json
- `bin/mail version` 调用：显示本地 + 线上 + since_local 的 diff 段
"""
from __future__ import annotations

from typing import Any, Dict


def fetch(as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")


def version_overview(as_json: bool = False) -> Dict[str, Any]:
    """返回 {local, latest, pending_changes: [...]}"""
    raise NotImplementedError("P0-9")
