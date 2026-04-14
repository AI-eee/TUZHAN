"""lib.send — 发件（P0-9 实现）。

流程：
  1. 参数校验（--to、--content 必填）
  2. 昵称 → emp_id 模糊匹配（在 data/contacts/roster.md 中查）
     - 命中 0 个：报 no_match
     - 命中 >1 个 且非精确：进入 --confirm 交互或结构化报错（--json 下直接报错）
  3. 如 --reply-to，查找原 msg 的 thread_id / frontmatter 继承
  4. frontmatter 合并（客户端注入 thread_id / in_reply_to）
  5. POST /mail/api/messages/send（如 --require-approval 则走 /approve/request）
  6. 落盘到 data/outbox/<receiver_emp_id>/<msg_id>.md
"""
from __future__ import annotations

from typing import Any, Dict


def run(args: Any, as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")
