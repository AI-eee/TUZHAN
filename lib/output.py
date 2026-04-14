"""lib.output — human / json 双输出 + 结构化日志落盘。

所有子命令必须用本模块的 emit_ok / emit_error，禁止 print / raise 到用户面前。
- --json 时：纯 JSON 到 stdout，不含 ANSI
- 人读模式：有 rich 则用 rich 渲染（彩色 + 表格），无 rich 则 fallback 到 stdlib

每次命令调用都会在 data/logs/mail.log 落一行 JSON（滚动由 doctor 维护）。
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, Optional

from lib.errors import MailError


def _log_event(event: Dict[str, Any]) -> None:
    """尽力而为：写一行 JSON 到 data/logs/mail.log。任何失败都静默。"""
    try:
        from lib import paths

        log_path = paths.mail_log()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **event}, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 日志失败永远不影响主流程


def _rich_console():
    """懒加载 rich.Console；不可用则返回 None。"""
    try:
        from rich.console import Console

        return Console(highlight=False)
    except ImportError:
        return None


def emit_ok(payload: Dict[str, Any], *, as_json: bool = False, command: Optional[str] = None) -> None:
    """成功输出。payload 必须可 JSON 序列化。"""
    data = {"ok": True, **payload}
    _log_event({"level": "info", "command": command, "ok": True, "summary": _summarize(payload)})

    if as_json:
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
        return

    console = _rich_console()
    if console is None:
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return

    # rich 人读模式：顶部绿勾 + payload 展平为 key=value
    console.print(f"[bold green]✓[/] {command or 'ok'}")
    for k, v in payload.items():
        if isinstance(v, (dict, list)):
            console.print(f"  [dim]{k}[/] = {json.dumps(v, ensure_ascii=False)}")
        else:
            console.print(f"  [dim]{k}[/] = {v}")


def emit_error(err: MailError, *, as_json: bool = False, command: Optional[str] = None) -> None:
    """错误输出。总是写到 stderr；exit code 由 caller 按 err.exit_code 自行设置。"""
    _log_event({"level": "error", "command": command, "ok": False, "code": err.code, "message": err.message})

    if as_json:
        sys.stderr.write(json.dumps(err.to_dict(), ensure_ascii=False) + "\n")
        return

    console = _rich_console()
    if console is None:
        sys.stderr.write(str(err) + "\n")
        if err.hint:
            sys.stderr.write(f"  → 建议：{err.hint}\n")
        return

    # rich 人读模式：红色错误 + 黄色建议
    console.print(f"[bold red]✗[/] [red]{err.code}[/]: {err.message}", highlight=False)
    if err.hint:
        console.print(f"  [yellow]→ 建议：[/]{err.hint}", highlight=False)
    if err.context:
        console.print(f"  [dim]context:[/] {json.dumps(err.context, ensure_ascii=False)}")


def _summarize(payload: Dict[str, Any]) -> Dict[str, Any]:
    """截断 payload 里体积大的字段（body / messages），只留摘要进日志。"""
    out = {}
    for k, v in payload.items():
        if k in ("body", "content", "messages", "files"):
            if isinstance(v, (list, tuple)):
                out[k] = f"<{type(v).__name__} len={len(v)}>"
            elif isinstance(v, str):
                out[k] = f"<str len={len(v)}>"
            else:
                out[k] = f"<{type(v).__name__}>"
        else:
            out[k] = v
    return out
