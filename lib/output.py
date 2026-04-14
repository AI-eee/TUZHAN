"""lib.output — human / json 双输出。

所有子命令必须用本模块的 emit_ok / emit_error，禁止 print/raise 到用户面前。
这样：
- --json 时输出纯 JSON 到 stdout，不含 ANSI
- 人读模式用 rich 输出彩色表格 / 段落

P0-2 负责真实实现 + rich 接入。skeleton 阶段先纯 stdlib 可用版本。
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict

from lib.errors import MailError


def emit_ok(payload: Dict[str, Any], *, as_json: bool = False) -> None:
    """成功输出。payload 必须可 JSON 序列化。"""
    data = {"ok": True, **payload}
    if as_json:
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    else:
        # TODO(P0-2): 用 rich 做人读友好渲染
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def emit_error(err: MailError, *, as_json: bool = False) -> None:
    """错误输出。总是写到 stderr；exit code 由 caller 按 err.exit_code 自行设置。"""
    if as_json:
        sys.stderr.write(json.dumps(err.to_dict(), ensure_ascii=False) + "\n")
    else:
        # TODO(P0-2): 用 rich 做红色高亮
        sys.stderr.write(str(err) + "\n")
        if err.hint:
            sys.stderr.write(f"  → 建议：{err.hint}\n")
