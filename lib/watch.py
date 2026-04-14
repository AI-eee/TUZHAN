"""lib.watch — 守护模式（P0-9 实现）。

职责：
- 循环调用 sync.run()，间隔 --interval（默认 30s，下限 5s）
- 收到 SIGTERM / SIGINT → graceful shutdown，落盘当前 since 游标
- 错误：连续 N 次 connectivity_fail → exponential backoff 到 60s
- 被熔断（circuit_open）→ 立即退出（不要继续骚扰服务端），exit code 75
"""
from __future__ import annotations

from typing import Any, Dict


def run(interval: int = 30, as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")
