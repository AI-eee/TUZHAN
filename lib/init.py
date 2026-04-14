"""lib.init — 首次初始化（P0-3 实现）。

流程：
  1. 幂等检查 data/.installed.flag，已 init 过直接跳过
  2. 建 data/{inbox,outbox,contacts,cache/{staging,backup},logs} 目录
  3. 写 data/config.toml 模板（chmod 0600）
  4. 检测 requirements.txt 依赖，缺失则 pip install --user
  5. 跑一次 doctor.run() 确保环境可用
  6. 写 data/.installed.flag（内容：时间戳 + 版本 + python 版本）
"""
from __future__ import annotations

from typing import Any, Dict


def run(as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-3: 实现 init 流程")
