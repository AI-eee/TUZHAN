"""lib.paths — Skill 根与 data/ 路径解析。

设计原则：
- 零 env 入口：Skill 根基于 __file__ 解析，不依赖 TUZHAN_WORKSPACE
- profile 参数预留（v3.0 固定 "default"，v3.1 起支持 --profile）
- 用 pathlib，为 v3.x Windows 留口子

P0-2 负责实现。skeleton 阶段仅提供常量。
"""
from __future__ import annotations

from pathlib import Path

# 本文件位于 lib/paths.py，Skill 根 = 上两级
SKILL_ROOT: Path = Path(__file__).resolve().parent.parent

VERSION_FILE: Path = SKILL_ROOT / "VERSION"
MANIFEST_FILE: Path = SKILL_ROOT / "manifest.json"
SKILL_MD: Path = SKILL_ROOT / "SKILL.md"


def data_dir(profile: str = "default") -> Path:
    """返回 profile 对应的 data 目录（v3.0 恒为 SKILL_ROOT/data）"""
    if profile != "default":
        # 为 v3.1 预留：SKILL_ROOT / "data-profiles" / profile
        raise NotImplementedError("v3.0 仅支持 default profile，v3.1 起开放 --profile")
    return SKILL_ROOT / "data"


def config_toml(profile: str = "default") -> Path:
    return data_dir(profile) / "config.toml"


def installed_flag(profile: str = "default") -> Path:
    return data_dir(profile) / ".installed.flag"


def inbox_dir(profile: str = "default") -> Path:
    return data_dir(profile) / "inbox"


def outbox_dir(profile: str = "default") -> Path:
    return data_dir(profile) / "outbox"


def roster_md(profile: str = "default") -> Path:
    return data_dir(profile) / "contacts" / "roster.md"


def cache_dir(profile: str = "default") -> Path:
    return data_dir(profile) / "cache"


def staging_dir(profile: str = "default") -> Path:
    return cache_dir(profile) / "staging"


def backup_dir(profile: str = "default") -> Path:
    return cache_dir(profile) / "backup"


def logs_dir(profile: str = "default") -> Path:
    return data_dir(profile) / "logs"


def mail_log(profile: str = "default") -> Path:
    return logs_dir(profile) / "mail.log"
