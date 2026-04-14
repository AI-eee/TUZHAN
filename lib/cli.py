"""lib.cli — argparse 顶层分发器。

skeleton 阶段：所有子命令已占位注册，实现走各自 lib/<cmd>.py。未实现的子命令统一
通过 errors.NotImplementedYet 结构化报错，不使用裸 NotImplementedError。

P0-3 负责接入真实的 init + doctor 实现；P0-9 负责业务命令。
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from lib import __version__


_SUBCOMMANDS = [
    ("init", "首次初始化 Skill（建 data/、写 config 模板、跑 doctor）"),
    ("doctor", "9 项环境体检"),
    ("sync", "收发件同步"),
    ("send", "发件"),
    ("list", "拉取项目 + 花名册"),
    ("ack", "收件方推进 5 态回执"),
    ("trace", "发件方查询全链路状态"),
    ("watch", "守护模式轮询"),
    ("update", "自更新（原子替换 + 回滚）"),
    ("rollback", "从 data/cache/backup/ 原子恢复"),
    ("version", "本地 + 线上 + changelog"),
    ("help", "自描述（命令 + 错误码表）"),
    ("profile", "能力声明（set / get）"),
    ("directory", "按能力搜索 Agent"),
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bin/mail",
        description=f"TUZHAN Agent Mail 客户端（{__version__}）",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    for name, help_text in _SUBCOMMANDS:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--json", action="store_true", help="结构化 JSON 输出（Agent 友好）")
        sp.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.command:
        parser.print_help()
        return 1

    # TODO(P0-3/P0-9): 将每个命令 dispatch 到 lib.<command>.run(args)
    from lib.errors import NotImplementedYet
    from lib.output import emit_error

    err = NotImplementedYet(
        command=args.command,
        hint="v3.0.0 skeleton 阶段，此命令尚未实现。请等待 P0-3 / P0-9 批次。",
    )
    emit_error(err, as_json=getattr(args, "json", False))
    return err.exit_code


if __name__ == "__main__":
    sys.exit(main())
