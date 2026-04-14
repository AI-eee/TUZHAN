"""lib.update — 原子自更新 + 自动回滚（P0-9 实现，见 PRD §2.3）。

流程：
  1. GET /mail/api/version → {version, manifest_url, zip_url, sha256}
  2. 本地 == 线上？是 → 直接返回 up_to_date
  3. 下载 zip 到 data/cache/staging/incoming.zip
  4. SHA256 校验；不通过 → 删 staging + 报 checksum_fail
  5. zipslip 保护解压到 data/cache/staging/v.NEW/
  6. 在 staging 跑 doctor self-test；失败 → 删 staging + 报 self_test_fail
  7. 原子替换：
     a. cp -r 当前 SKILL.md/lib/bin/VERSION/manifest.json → data/cache/backup/v.OLD/
     b. 对每个文件：rename 当前 → .old；rename staging → 当前
  8. 再跑一次 doctor 验证；失败 → 把 .old rename 回原位 → 报 post_update_fail（原子回滚）
  9. 清理 .old 文件 + staging，输出 changelog
"""
from __future__ import annotations

from typing import Any, Dict


def run(check_only: bool = False, as_json: bool = False) -> Dict[str, Any]:
    raise NotImplementedError("P0-9")


def rollback(to_version: str = "", as_json: bool = False) -> Dict[str, Any]:
    """从 data/cache/backup/v{old}/ 原子恢复（默认恢复最近一次）。"""
    raise NotImplementedError("P0-9")
