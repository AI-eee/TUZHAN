#!/usr/bin/env python3
"""notify_webhook.py — POST HMAC 签名 webhook 到 SEE2AI `/mail/api/internal/version-bump`。

用法：
  python3 scripts/ci/notify_webhook.py v3.0.0

必需环境变量：
  SEE2AI_WEBHOOK_URL      — 完整 URL，例如 https://see2ai.example.com/mail/api/internal/version-bump
  SEE2AI_WEBHOOK_SECRET   — HMAC-SHA256 密钥

依赖 GITHUB_OUTPUT（由前一步 upload_release.py 写入）或手动 env：
  ZIP_URL
  MANIFEST_URL
  ZIP_SHA256

行为：
  - 构建 body = {version, zip_url, manifest_url, sha256, released_at}
  - 计算 X-Signature: sha256=<hex(hmac(body, secret))>
  - 头部 X-Timestamp: unix seconds
  - 失败不使 CI 整体失败（print 警告，exit 0）—— 允许 SEE2AI 侧滞后实现
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: notify_webhook.py <version>", file=sys.stderr)
        return 2

    version = sys.argv[1]

    url = os.environ.get("SEE2AI_WEBHOOK_URL", "").strip()
    secret = os.environ.get("SEE2AI_WEBHOOK_SECRET", "").strip()
    if not url or not secret:
        print("[notify] 未配置 SEE2AI_WEBHOOK_URL / SEE2AI_WEBHOOK_SECRET，跳过通知")
        return 0

    zip_url = os.environ.get("ZIP_URL", "").strip()
    manifest_url = os.environ.get("MANIFEST_URL", "").strip()
    zip_sha256 = os.environ.get("ZIP_SHA256", "").strip()
    if not (zip_url and manifest_url and zip_sha256):
        print(f"[notify] 缺少 ZIP_URL / MANIFEST_URL / ZIP_SHA256，无法通知（继续）")
        return 0

    body = {
        "version": version,
        "zip_url": zip_url,
        "manifest_url": manifest_url,
        "sha256": zip_sha256,
        "released_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        url,
        data=body_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Signature": f"sha256={sig}",
            "X-Timestamp": timestamp,
            "User-Agent": f"tuzhan-ci/{version}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.getcode()
            body_resp = resp.read().decode("utf-8", errors="replace")
        print(f"[notify] {url} → HTTP {code}: {body_resp[:200]}")
    except urllib.error.HTTPError as e:
        print(f"[notify] warning: HTTP {e.code}：{e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        print(f"[notify] warning: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
