#!/usr/bin/env python3
"""upload_release.py — 把 dist/ 里的 zip + manifest.json 上传到 S3 兼容 OSS。

用法：
  python3 scripts/ci/upload_release.py v3.0.0

必需环境变量：
  OSS_ENDPOINT   — 例如 https://oss-cn-hangzhou.aliyuncs.com
  OSS_ACCESS_KEY
  OSS_SECRET_KEY
  OSS_BUCKET
  OSS_PREFIX     — 可选，默认 "releases/"
  OSS_PUBLIC_URL — 可选；若设置，最终 URL 用此 base；否则用 bucket.endpoint/key

产物 URL 会写入 GITHUB_OUTPUT（zip_url / manifest_url）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = PROJECT_ROOT / "dist"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: upload_release.py <version>", file=sys.stderr)
        return 2

    version = sys.argv[1]

    for key in ("OSS_ENDPOINT", "OSS_ACCESS_KEY", "OSS_SECRET_KEY", "OSS_BUCKET"):
        if not os.environ.get(key):
            print(f"error: 缺少环境变量 {key}", file=sys.stderr)
            return 3

    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as e:
        print(f"error: 需要 boto3（pip install boto3）：{e}", file=sys.stderr)
        return 4

    endpoint = os.environ["OSS_ENDPOINT"].rstrip("/")
    access_key = os.environ["OSS_ACCESS_KEY"]
    secret_key = os.environ["OSS_SECRET_KEY"]
    bucket = os.environ["OSS_BUCKET"]
    prefix = os.environ.get("OSS_PREFIX", "releases/").lstrip("/").rstrip("/") + "/"
    public_base = os.environ.get("OSS_PUBLIC_URL", "").rstrip("/")

    zip_path = DIST_DIR / f"tuzhan-agent-mail-{version}.zip"
    manifest_path = DIST_DIR / "manifest.json"
    for p in (zip_path, manifest_path):
        if not p.exists():
            print(f"error: {p} 不存在，请先运行 build_release.py", file=sys.stderr)
            return 5

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3", s3={"addressing_style": "virtual"}),
    )

    zip_key = f"{prefix}{version}/tuzhan-agent-mail-{version}.zip"
    manifest_key = f"{prefix}{version}/manifest.json"

    _put(s3, bucket, zip_key, zip_path.read_bytes(), "application/zip")
    _put(s3, bucket, manifest_key, manifest_path.read_bytes(), "application/json")

    if public_base:
        zip_url = f"{public_base}/{zip_key}"
        manifest_url = f"{public_base}/{manifest_key}"
    else:
        scheme, _, host = endpoint.partition("://")
        zip_url = f"{scheme}://{bucket}.{host}/{zip_key}"
        manifest_url = f"{scheme}://{bucket}.{host}/{manifest_key}"

    print(f"[upload] zip      → {zip_url}")
    print(f"[upload] manifest → {manifest_url}")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"zip_url={zip_url}\n")
            f.write(f"manifest_url={manifest_url}\n")

    return 0


def _put(s3, bucket: str, key: str, body: bytes, content_type: str) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    print(f"[upload] {key} ({len(body)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
