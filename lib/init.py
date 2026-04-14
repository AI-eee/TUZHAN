"""lib.init — 首次初始化（P0-3 实现）。

流程：
  1. 幂等：如果 data/.installed.flag 存在且内容有效，直接返回 already_initialized
  2. 建 data/{inbox,outbox,contacts,cache/{staging,backup},logs}
  3. 写 data/config.toml 模板（chmod 0600）
  4. 尝试安装 requirements.txt（best-effort，失败不阻塞，但明确告知）
  5. 跑一次 doctor（autofix=True），整体 fail 也不阻塞 init 本身
  6. 写 data/.installed.flag，记录 {ts, version, python, skill_root}
  7. 返回结构化结果

设计权衡：
- 依赖安装失败不阻塞 init（很多生产机器默认无公网），但会在返回的 warnings 里标记
- doctor fail 不阻塞 init（允许先创建结构，后修理 API_KEY / 网络），但同样进 warnings
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

from lib import paths
from lib.output import emit_ok


_CONFIG_TOML_TEMPLATE = """# TUZHAN Agent Mail 客户端本地配置
# 自动生成于首次 bin/mail init。环境变量永远优先，此处仅作兜底。
# 本文件默认权限 0600，请不要改宽；也不要 commit 进任何 git 仓库。

[auth]
# 你的私钥（从 SEE2AI 管理员处获取；也可以 export TUZHAN_API_KEY 覆盖本值）
api_key = ""

# 邮件服务端 base URL，例如 "https://see2ai.example.com/mail/api"
api_base = ""

[client]
# watch 守护模式默认轮询间隔（秒），服务端最小下限 5
watch_interval_s = 30

# 收发件保留天数；超过自动清理 data/{inbox,outbox}/**
retention_days = 30
"""


def run(*, as_json: bool = False) -> int:
    """执行 init 流程并 emit。返回 exit code。"""
    warnings: List[str] = []
    actions: List[str] = []

    flag_file = paths.installed_flag()
    if flag_file.exists():
        try:
            prev = json.loads(flag_file.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
        emit_ok({
            "status": "already_initialized",
            "installed_at": prev.get("ts"),
            "previous_version": prev.get("version"),
            "hint": "如需重新初始化，请手动删除 data/.installed.flag",
        }, as_json=as_json, command="init")
        return 0

    # Step 2: data/ 目录
    try:
        paths.ensure_data_dirs()
        actions.append("ensured data/ directory tree")
    except Exception as e:
        warnings.append(f"ensure_data_dirs 失败：{e}")

    # Step 3: config.toml 模板
    cfg = paths.config_toml()
    if not cfg.exists():
        try:
            cfg.write_text(_CONFIG_TOML_TEMPLATE, encoding="utf-8")
            if os.name == "posix":
                cfg.chmod(0o600)
            actions.append(f"wrote config template {cfg.relative_to(paths.SKILL_ROOT)} (0600)")
        except Exception as e:
            warnings.append(f"写 config.toml 失败：{e}")

    # Step 4: bootstrap 依赖
    if os.environ.get("TUZHAN_SKIP_BOOTSTRAP", "").strip() in ("1", "true", "yes"):
        warnings.append("TUZHAN_SKIP_BOOTSTRAP 生效，已跳过依赖自动安装")
    else:
        boot = _bootstrap_deps()
        if boot["status"] == "ok":
            actions.append(f"pip install --user: {boot['installed']} packages")
        elif boot["status"] == "skipped":
            actions.append(f"deps already present: {boot['reason']}")
        else:
            warnings.append(f"pip install 失败（不阻塞）：{boot['reason']}")

    # Step 5: doctor（autofix=True，但容忍 fail）
    doctor_summary = "skipped"
    try:
        from lib.doctor import run as run_doctor
        # 我们要拿到结构化结果而不是让 doctor 直接 emit，所以另走一遍
        # TODO(P0-3.1): 把 doctor.run 改成返回 dict，由 cli 决定 emit；
        # 现版本为减少改动，把 doctor 当黑盒调用，init 只记录整体状态
        # 不在 init 里打印 doctor 细节，避免重复输出
        doctor_summary = "ok" if _silent_doctor() else "has_failures"
        if doctor_summary == "has_failures":
            warnings.append("doctor 存在失败项，请 bin/mail doctor --verbose 查看")
    except Exception as e:
        warnings.append(f"doctor 未能执行：{e}")

    # Step 6: .installed.flag
    flag_payload = {
        "ts": time.time(),
        "version": paths.read_version(),
        "python": f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}",
        "skill_root": str(paths.SKILL_ROOT),
    }
    try:
        flag_file.write_text(json.dumps(flag_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        actions.append(".installed.flag written")
    except Exception as e:
        warnings.append(f"写 .installed.flag 失败：{e}")

    emit_ok({
        "status": "initialized",
        "actions": actions,
        "warnings": warnings,
        "doctor": doctor_summary,
        "next": ["bin/mail doctor", "bin/mail sync"] if doctor_summary == "ok"
                else ["检查上方 warnings", "bin/mail doctor --verbose 修复后再发邮件"],
    }, as_json=as_json, command="init")
    return 0


def _silent_doctor() -> bool:
    """跑一次 doctor 但不打印，返回 True 表示全 pass。

    P0-3.1 重构：把 doctor.run 改成纯函数返回 dict；现版本临时吞掉 stdout/stderr。
    """
    # 暂存 stdout/stderr
    import io

    stdout_bak, stderr_bak = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        from lib.doctor import run as run_doctor
        rc = run_doctor(as_json=True, verbose=True, autofix=True)
        return rc == 0
    finally:
        sys.stdout, sys.stderr = stdout_bak, stderr_bak


def _bootstrap_deps() -> Dict[str, Any]:
    """best-effort pip install --user -r requirements.txt。

    返回 {status: ok|skipped|fail, installed: N, reason: str}。
    已装过则通过 import 探测短路（避免 pip 重跑 5s 加载）。
    """
    req_file = paths.SKILL_ROOT / "requirements.txt"
    if not req_file.exists():
        return {"status": "skipped", "reason": "requirements.txt 不存在", "installed": 0}

    # 快速探测：核心依赖全部 importable 就不跑 pip
    core_mods = {
        "httpx": "httpx",
        "rich": "rich",
        "frontmatter": "python-frontmatter",
    }
    missing = []
    for mod_name, pkg_name in core_mods.items():
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pkg_name)

    # tomli 只在 <3.11 需要
    if sys.version_info < (3, 11):
        try:
            __import__("tomli")
        except ImportError:
            missing.append("tomli")
        try:
            __import__("tomli_w")
        except ImportError:
            missing.append("tomli_w")

    if not missing:
        return {"status": "skipped", "reason": "all deps present", "installed": 0}

    cmd = [sys.executable, "-m", "pip", "install", "--user", "-r", str(req_file)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"status": "fail", "reason": "pip install timeout (120s)", "installed": 0}
    except Exception as e:
        return {"status": "fail", "reason": f"{type(e).__name__}: {e}", "installed": 0}

    if r.returncode != 0:
        # 截取最后 5 行 stderr 作为 reason
        tail = "\n".join(r.stderr.strip().splitlines()[-5:])
        return {"status": "fail", "reason": f"pip exit {r.returncode}\n{tail}", "installed": 0}

    return {"status": "ok", "reason": "", "installed": len(missing)}
