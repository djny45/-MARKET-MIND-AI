"""Minimal S3-compatible off-host backup adapter (stdlib only).

Credentials are read ONLY from environment variables and are never printed or
written to disk. This is a safe prerequisite for an operator-hosted deployment;
it does not claim that a real S3 bucket or credentials exist in this repository.

Required environment:
  MARKET_MIND_S3_ENDPOINT   e.g. https://s3.amazonaws.com or https://minio.internal:9000
  MARKET_MIND_S3_BUCKET     bucket name
  MARKET_MIND_S3_REGION     e.g. us-east-1
  MARKET_MIND_S3_ACCESS_KEY  access key id
  MARKET_MIND_S3_SECRET_KEY  secret access key

Optional:
  MARKET_MIND_S3_PREFIX     key prefix (default: market-mind/backups)
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import Path


def _settings() -> dict[str, str]:
    keys = (
        "MARKET_MIND_S3_ENDPOINT", "MARKET_MIND_S3_BUCKET",
        "MARKET_MIND_S3_REGION", "MARKET_MIND_S3_ACCESS_KEY",
        "MARKET_MIND_S3_SECRET_KEY",
    )
    missing = [key for key in keys if not os.getenv(key, "").strip()]
    if missing:
        raise SystemExit(
            "missing S3 environment variables: " + ", ".join(missing) +
            " (values are never printed)"
        )
    return {key: os.environ[key].strip() for key in keys}


def _sign(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _authorization(method: str, host: str, path: str, payload: bytes, settings: dict) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    region = settings["MARKET_MIND_S3_REGION"]
    scope = f"{datestamp}/{region}/s3/aws4_request"
    payload_hash = hashlib.sha256(payload).hexdigest()
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amzdate,
    }
    canonical_headers = "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers))
    signed_headers = ";".join(sorted(headers))
    canonical_request = "\n".join([
        method, path, "", canonical_headers, signed_headers, payload_hash,
    ])
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amzdate, scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signing_key = _sign(
        _sign(_sign(_sign(("AWS4" + settings["MARKET_MIND_S3_SECRET_KEY"]).encode(), datestamp), region), "s3"),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={settings['MARKET_MIND_S3_ACCESS_KEY']}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return headers


def _request(method: str, url: str, payload: bytes, settings: dict, host: str, path: str):
    headers = _authorization(method, host, path, payload, settings)
    request = urllib.request.Request(url, data=payload or None, method=method)
    for name, value in headers.items():
        request.add_header(name, value)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upload", "download", "describe-config"))
    parser.add_argument("--file", help="local file to upload or destination for download")
    parser.add_argument("--key", help="object key (defaults to file name under the prefix)")
    parser.add_argument("--dry-run", action="store_true", help="validate env and print a secret-free plan")
    args = parser.parse_args(argv)
    settings = _settings()
    endpoint = settings["MARKET_MIND_S3_ENDPOINT"].rstrip("/")
    bucket = settings["MARKET_MIND_S3_BUCKET"]
    prefix = os.getenv("MARKET_MIND_S3_PREFIX", "market-mind/backups").strip("/")
    if args.action == "describe-config":
        print(json.dumps({
            "endpoint": endpoint, "bucket": bucket, "region": settings["MARKET_MIND_S3_REGION"],
            "prefix": prefix, "credentials_present": True, "credentials_exposed": False,
            "dry_run": args.dry_run,
        }, sort_keys=True))
        return 0
    if not args.file:
        raise SystemExit("--file is required for upload/download")
    key = args.key or f"{prefix}/{Path(args.file).name}"
    path = f"/{bucket}/{key}"
    url = endpoint + path
    if args.dry_run:
        print(json.dumps({"action": args.action, "file": args.file, "key": key,
                          "url": url, "credentials_exposed": False}, sort_keys=True))
        return 0
    if args.action == "upload":
        payload = Path(args.file).read_bytes()
        status, _ = _request("PUT", url, payload, settings, urlparse(endpoint).netloc, path)
    else:
        status, payload = _request("GET", url, b"", settings, urlparse(endpoint).netloc, path)
        Path(args.file).write_bytes(payload)
    print(json.dumps({"action": args.action, "status": status, "key": key,
                      "credentials_exposed": False}, sort_keys=True))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
