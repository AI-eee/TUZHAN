"""
TUZHAN SQLite 数据库每日备份
============================
原则：小而健壮、零依赖、原子操作。

特性：
1. 使用 SQLite 官方 .backup() API 进行**热备份**——即使服务器正在写入，
   备份文件也是事务一致的，绝不会拷到一个半截的写事务（这是 cp 命令做不到的）。
2. 备份文件命名为 prod_2026-04-07.sqlite，按日期天然去重。
3. 自动清理超过保留天数的旧备份（默认 14 天）。
4. 适配 .env 中的 TUZHAN_ENV，development 备份 dev.sqlite，production 备份 prod.sqlite。
5. 退出码：0 成功，非 0 失败 —— 便于 cron 失败时被监控感知。

使用：
    python3 scripts/backup_db.py                       # 备份当前 .env 指定环境
    python3 scripts/backup_db.py --env production
    python3 scripts/backup_db.py --keep-days 30        # 自定义保留天数

推荐 crontab（每天凌晨 3:00 执行）：
    0 3 * * * cd /path/to/TUZHAN && /usr/bin/python3 scripts/backup_db.py --env production >> data/backup/backup.log 2>&1
"""
import argparse
import os
import sqlite3
import sys
import yaml
from datetime import datetime, timedelta
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def resolve_db_path(env: str) -> str:
    settings_file = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
    with open(settings_file, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    db_url = settings.get(env, settings["development"])["database_url"]
    db_path = db_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = os.path.join(PROJECT_ROOT, db_path[2:])
    return os.path.abspath(db_path)


def backup(env: str, keep_days: int) -> int:
    src_path = resolve_db_path(env)
    if not os.path.exists(src_path):
        print(f"[ERROR] 数据库文件不存在: {src_path}", file=sys.stderr)
        return 2

    backup_dir = os.path.join(PROJECT_ROOT, "data", "backup")
    os.makedirs(backup_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    db_basename = os.path.splitext(os.path.basename(src_path))[0]
    dst_path = os.path.join(backup_dir, f"{db_basename}_{today}.sqlite")
    tmp_path = dst_path + ".part"

    # 1. 用 SQLite 官方 backup API 做事务一致的热备份
    try:
        src = sqlite3.connect(src_path)
        dst = sqlite3.connect(tmp_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        print(f"[ERROR] 备份失败: {e}", file=sys.stderr)
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return 3

    # 2. 原子重命名，避免在 .part 状态被外部读取
    os.replace(tmp_path, dst_path)
    size_kb = os.path.getsize(dst_path) // 1024
    print(f"[OK] 备份完成: {dst_path} ({size_kb} KB)")

    # 3. 清理过期备份
    cutoff = datetime.now() - timedelta(days=keep_days)
    purged = 0
    for fname in os.listdir(backup_dir):
        if not fname.startswith(f"{db_basename}_") or not fname.endswith(".sqlite"):
            continue
        full = os.path.join(backup_dir, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(full))
            if mtime < cutoff:
                os.remove(full)
                purged += 1
        except OSError:
            continue
    if purged:
        print(f"[OK] 已清理 {purged} 个超过 {keep_days} 天的旧备份")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TUZHAN SQLite 每日备份工具")
    parser.add_argument("--env", choices=["development", "production"], default=None,
                        help="目标环境 (默认从 .env 的 TUZHAN_ENV 读取)")
    parser.add_argument("--keep-days", type=int, default=14, help="备份保留天数 (默认 14 天)")
    args = parser.parse_args()
    env = args.env or os.getenv("TUZHAN_ENV", "development")
    sys.exit(backup(env, args.keep_days))
