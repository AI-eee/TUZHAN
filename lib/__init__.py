"""TUZHAN Agent Mail v3 客户端 lib 包。

所有业务模块集合处，bin/mail 通过 from lib.cli import main 进入。

设计约束（PRD-0054 §0.5）：
- 单文件 ≤ 300 行
- 每个模块单一职责
- 所有命令支持 --json
- 错误码统一走 lib.errors
"""

__version__ = "v3.0.0-dev"
