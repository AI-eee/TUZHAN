#!/usr/bin/env python3
"""build_release.py — 打包 v3 客户端 Skill 为 zip + 生成 manifest.json + changelog.json。

用法：
  python3 scripts/ci/build_release.py v3.0.0

产物（写入 dist/）：
  - tuzhan-agent-mail-v3.0.0.zip       （Skill 打包）
  - manifest.json                       （每个文件的 SHA256 + version + released_at）
  - changelog.json                      （基于 git log 的 changelog，追加到仓库根）
  - release.sha256                       （zip 本体 SHA256，用于 /version endpoint）

白名单（进入 zip 的文件）：
  - SKILL.md / VERSION / .gitignore / requirements.txt / manifest.json
  - bin/mail / lib/*.py / docs/*.md

明确排除：scripts/ci/、.github/、README.md、data/、tests/、任何 __pycache__。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = PROJECT_ROOT / "dist"


INCLUDE_GLOBS = [
    "SKILL.md",
    "VERSION",
    ".gitignore",
    "requirements.txt",
    "bin/mail",
    "lib/*.py",
    "docs/*.md",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _collect_files() -> List[Path]:
    files: List[Path] = []
    for pattern in INCLUDE_GLOBS:
        for f in PROJECT_ROOT.glob(pattern):
            if f.is_file() and "__pycache__" not in f.parts:
                files.append(f)
    return sorted(set(files))


def _build_manifest(version: str, files: List[Path]) -> Dict:
    entries = []
    for f in files:
        data = f.read_bytes()
        rel = str(f.relative_to(PROJECT_ROOT))
        entries.append({"path": rel, "sha256": _sha256(data), "size": len(data)})
    return {
        "version": version,
        "released_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": entries,
    }


def _build_zip(version: str, files: List[Path], manifest: Dict) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    zip_path = DIST_DIR / f"tuzhan-agent-mail-{version}.zip"

    # manifest.json 也要进 zip，但内容是刚算出来的 manifest
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            rel = str(f.relative_to(PROJECT_ROOT))
            zf.write(f, f"tuzhan_agent_mail/{rel}")
        zf.writestr("tuzhan_agent_mail/manifest.json", manifest_bytes)

    return zip_path


def _git_changelog(from_tag: str = "", to_tag: str = "HEAD") -> List[Dict]:
    """拉取 from_tag..to_tag 之间的 commits。from_tag 为空 → 全部 history。"""
    range_spec = f"{from_tag}..{to_tag}" if from_tag else to_tag
    try:
        r = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "log", "--pretty=format:%H|%ci|%s", range_spec],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"warning: git log 失败：{e.stderr}", file=sys.stderr)
        return []

    commits = []
    for line in r.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({"sha": parts[0], "at": parts[1], "subject": parts[2]})
    return commits


def _prev_tag(version: str) -> str:
    """找上一个 v* tag（按 git describe），若无则返回空。"""
    try:
        r = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "describe", "--tags", "--abbrev=0",
             f"{version}^"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _upsert_changelog(version: str, commits: List[Dict]) -> Path:
    """生成/更新仓库根 changelog.json（追加或替换当前 version 的条目）。"""
    path = PROJECT_ROOT / "changelog.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"versions": []}

    entry = {
        "version": version,
        "released_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commits": commits,
    }
    # 去重：如果已有该 version，替换
    data["versions"] = [v for v in data["versions"] if v.get("version") != version]
    data["versions"].insert(0, entry)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: build_release.py <version>", file=sys.stderr)
        return 2

    version = sys.argv[1]
    if not version.startswith("v"):
        print(f"warning: version `{version}` 不以 v 开头，继续但请确认", file=sys.stderr)

    # 1. 校验 VERSION 文件一致
    version_file = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if version_file != version:
        print(f"error: VERSION 文件内容 `{version_file}` 与 tag `{version}` 不一致。请先更新 VERSION 再打 tag。", file=sys.stderr)
        return 3

    # 2. 收集文件 + 构建 manifest
    files = _collect_files()
    print(f"[build] 收集到 {len(files)} 个文件")
    manifest = _build_manifest(version, files)

    # 3. 写 dist/manifest.json
    DIST_DIR.mkdir(exist_ok=True)
    manifest_path = DIST_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[build] manifest.json 生成：{manifest_path}")

    # 4. 打 zip
    zip_path = _build_zip(version, files, manifest)
    zip_sha256 = _sha256(zip_path.read_bytes())
    (DIST_DIR / "release.sha256").write_text(zip_sha256 + "\n", encoding="utf-8")
    print(f"[build] zip：{zip_path} ({zip_path.stat().st_size} bytes)")
    print(f"[build] zip SHA256：{zip_sha256}")

    # 5. 生成 changelog
    prev = _prev_tag(version)
    print(f"[changelog] 上一 tag：{prev or '<none>'} → {version}")
    commits = _git_changelog(from_tag=prev, to_tag=version) if prev else _git_changelog(to_tag=version)
    changelog_path = _upsert_changelog(version, commits)
    print(f"[changelog] 写入 {changelog_path}（{len(commits)} commits）")

    # 6. 输出到 GITHUB_OUTPUT（如果在 Actions 环境）
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"zip_path={zip_path}\n")
            f.write(f"zip_sha256={zip_sha256}\n")
            f.write(f"manifest_path={manifest_path}\n")
            f.write(f"version={version}\n")
        print(f"[output] 已写入 GITHUB_OUTPUT")

    return 0


if __name__ == "__main__":
    sys.exit(main())
