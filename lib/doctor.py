"""lib.doctor — 9 项环境体检 + autofix（P0-3 实现）。

9 项检查：
  1. python 版本 ≥ 3.10
  2. cwd == SKILL_ROOT（你必须在 Skill 根执行）
  3. .gitignore 已忽略 data/（防敏感信息入库）    [autofix]
  4. data/ 子目录结构完整                         [autofix]
  5. data/config.toml 存在 + 权限 0600            [autofix 权限]
  6. TUZHAN_API_KEY 可读（env 或 config.toml）
  7. 服务端连通性（GET /mail/api/health）          [依赖 6]
  8. 版本对比（本地 VERSION vs 线上 /version）      [依赖 7]
  9. 账号画像（GET /me 验证 API_KEY 有效）          [依赖 6 7]

每一项结果为 {id, name, status: pass|fail|skip|autofixed, detail, fix_applied}。
任一 fail → 整体 exit 70，Agent 可据 details 决定如何处理。
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib import paths
from lib.errors import MailError
from lib.output import emit_error, emit_ok


MIN_PYTHON = (3, 10)


def _check(name: str, status: str, detail: str = "", fix_applied: bool = False) -> Dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "fix_applied": fix_applied}


def run(*, as_json: bool = False, verbose: bool = False, autofix: bool = True) -> int:
    """执行体检并 emit。返回 exit code（0=全 pass，70=有 fail）。"""
    checks: List[Dict[str, Any]] = []

    checks.append(_c1_python_version())
    checks.append(_c2_cwd(autofix=False))  # cwd 不 autofix，只报告
    checks.append(_c3_gitignore(autofix=autofix))
    checks.append(_c4_data_dirs(autofix=autofix))
    checks.append(_c5_config_toml(autofix=autofix))
    checks.append(_c6_api_key())

    # 7 8 9 依赖连通性 —— 如果 6 fail 则直接 skip
    have_key = checks[5]["status"] == "pass"
    if have_key:
        c7 = _c7_connectivity()
        checks.append(c7)
        if c7["status"] == "pass":
            checks.append(_c8_version())
            checks.append(_c9_me())
        else:
            checks.append(_check("8. version", "skip", "依赖连通性通过"))
            checks.append(_check("9. me", "skip", "依赖连通性通过"))
    else:
        checks.append(_check("7. connectivity", "skip", "依赖 API_KEY 配置"))
        checks.append(_check("8. version", "skip", "依赖 API_KEY 配置"))
        checks.append(_check("9. me", "skip", "依赖 API_KEY 配置"))

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    skipped = sum(1 for c in checks if c["status"] == "skip")
    autofixed = sum(1 for c in checks if c["fix_applied"])

    payload = {
        "summary": {"pass": passed, "fail": failed, "skip": skipped, "autofixed": autofixed, "total": len(checks)},
        "checks": checks if verbose or as_json else [c for c in checks if c["status"] != "pass"],
        "overall": "healthy" if failed == 0 else "unhealthy",
    }
    emit_ok(payload, as_json=as_json, command="doctor")
    return 0 if failed == 0 else 70


# —— 9 项检查实现 ——

def _c1_python_version() -> Dict[str, Any]:
    cur = sys.version_info[:2]
    if cur >= MIN_PYTHON:
        return _check("1. python≥3.10", "pass", f"当前 {cur[0]}.{cur[1]}")
    return _check("1. python≥3.10", "fail",
                  f"当前 {cur[0]}.{cur[1]}，需 ≥3.10。请升级 python 或用 pyenv。")


def _c2_cwd(*, autofix: bool) -> Dict[str, Any]:
    cwd = Path.cwd().resolve()
    root = paths.SKILL_ROOT.resolve()
    if cwd == root:
        return _check("2. cwd==SKILL_ROOT", "pass", str(root))
    return _check("2. cwd==SKILL_ROOT", "fail",
                  f"当前 cwd={cwd}，需 cd 到 Skill 根 {root} 再执行")


def _c3_gitignore(*, autofix: bool) -> Dict[str, Any]:
    gi = paths.SKILL_ROOT / ".gitignore"
    try:
        content = gi.read_text(encoding="utf-8") if gi.exists() else ""
    except Exception as e:
        return _check("3. .gitignore 忽略 data/", "fail", f"读取失败：{e}")

    # 识别以 data/ 开头的条目（忽略注释）
    lines = [line.strip() for line in content.splitlines()]
    has_data = any(line == "data/" or line == "data" or line.startswith("data/") for line in lines if line and not line.startswith("#"))
    if has_data:
        return _check("3. .gitignore 忽略 data/", "pass")

    if not autofix:
        return _check("3. .gitignore 忽略 data/", "fail",
                      ".gitignore 未忽略 data/；请手工追加或重跑 bin/mail doctor（开启 autofix）")

    try:
        with gi.open("a", encoding="utf-8") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("\n# autofix by bin/mail doctor：禁止 data/ 入库\ndata/\n")
        return _check("3. .gitignore 忽略 data/", "autofixed", "已追加 data/ 条目", fix_applied=True)
    except Exception as e:
        return _check("3. .gitignore 忽略 data/", "fail", f"autofix 写入失败：{e}")


def _c4_data_dirs(*, autofix: bool) -> Dict[str, Any]:
    required = [
        paths.data_dir(), paths.inbox_dir(), paths.outbox_dir(),
        paths.data_dir() / "contacts", paths.cache_dir(),
        paths.staging_dir(), paths.backup_dir(), paths.logs_dir(),
    ]
    missing = [p for p in required if not p.exists()]
    if not missing:
        return _check("4. data/ 目录结构", "pass")
    if not autofix:
        return _check("4. data/ 目录结构", "fail",
                      f"缺失 {len(missing)} 个目录：{[str(p.relative_to(paths.SKILL_ROOT)) for p in missing]}")
    try:
        paths.ensure_data_dirs()
        return _check("4. data/ 目录结构", "autofixed", f"已补齐 {len(missing)} 个目录", fix_applied=True)
    except Exception as e:
        return _check("4. data/ 目录结构", "fail", f"autofix 失败：{e}")


def _c5_config_toml(*, autofix: bool) -> Dict[str, Any]:
    cfg = paths.config_toml()
    if not cfg.exists():
        return _check("5. data/config.toml", "fail",
                      "config.toml 不存在；请运行 bin/mail init 生成模板")

    if os.name == "posix":
        perm = stat.S_IMODE(cfg.stat().st_mode)
        if perm != 0o600:
            if autofix:
                try:
                    cfg.chmod(0o600)
                    return _check("5. data/config.toml (0600)", "autofixed",
                                  f"权限从 {oct(perm)} 修正为 0600", fix_applied=True)
                except Exception as e:
                    return _check("5. data/config.toml (0600)", "fail", f"chmod 失败：{e}")
            return _check("5. data/config.toml (0600)", "fail",
                          f"权限 {oct(perm)}，需 0600；重跑 doctor autofix 或手工 chmod")
    return _check("5. data/config.toml (0600)", "pass")


def _c6_api_key() -> Dict[str, Any]:
    if os.environ.get("TUZHAN_API_KEY", "").strip():
        return _check("6. TUZHAN_API_KEY", "pass", "来源：环境变量")
    # 尝试 config.toml
    try:
        from lib.api_client import _read_config_toml
        key, _ = _read_config_toml()
    except Exception as e:
        return _check("6. TUZHAN_API_KEY", "fail", f"读取 config.toml 失败：{e}")

    if key:
        return _check("6. TUZHAN_API_KEY", "pass", "来源：data/config.toml")
    return _check("6. TUZHAN_API_KEY", "fail",
                  "未配置 TUZHAN_API_KEY；export 环境变量或编辑 data/config.toml")


def _c7_connectivity() -> Dict[str, Any]:
    try:
        from lib.api_client import ApiClient
        with ApiClient() as c:
            r = c.health()
        return _check("7. 服务端连通性", "pass", f"/health → {r}")
    except MailError as e:
        return _check("7. 服务端连通性", "fail", f"[{e.code}] {e.message}")
    except Exception as e:
        return _check("7. 服务端连通性", "fail", f"{type(e).__name__}: {e}")


def _c8_version() -> Dict[str, Any]:
    try:
        from lib.api_client import ApiClient
        local = paths.read_version()
        with ApiClient() as c:
            r = c.get_version()
        remote = r.get("version") or r.get("latest") or "unknown"
        if str(local) == str(remote):
            return _check("8. 版本对比", "pass", f"local={local} == remote={remote}")
        return _check("8. 版本对比", "pass",
                      f"local={local} ≠ remote={remote}（可 bin/mail update 升级）")
    except MailError as e:
        return _check("8. 版本对比", "fail", f"[{e.code}] {e.message}")
    except Exception as e:
        return _check("8. 版本对比", "fail", f"{type(e).__name__}: {e}")


def _c9_me() -> Dict[str, Any]:
    try:
        from lib.api_client import ApiClient
        with ApiClient() as c:
            r = c.me()
        emp_id = r.get("emp_id") or r.get("id") or "?"
        return _check("9. 账号画像", "pass", f"emp_id={emp_id}")
    except MailError as e:
        return _check("9. 账号画像", "fail", f"[{e.code}] {e.message}")
    except Exception as e:
        return _check("9. 账号画像", "fail", f"{type(e).__name__}: {e}")
