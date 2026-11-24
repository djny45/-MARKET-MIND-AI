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
import time
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPSConnection, HTTPException
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
    findings = _s3_findings()
    if findings:
        raise SystemExit(
            "invalid S3 configuration: " + ", ".join(
                f"{item['variable']}:{item['issue']}" for item in findings
            ) + " (values are never printed)"
        )
    return {key: os.environ[key].strip() for key in keys}


def _s3_findings() -> list[dict]:
    from dr_common import validate_dr_environment
    return [
        item for item in validate_dr_environment(os.environ)["findings"]
        if item["variable"].startswith("MARKET_MIND_S3_")
    ]


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


def _request(method: str, url: str, payload: bytes, settings: dict, host: str, path: str,
             *, retries: int = 2, retry_delay: float = 0.2):
    """Send one signed request, retrying only transient failures.

    HTTP 4xx (especially 403 auth failures) are returned immediately; retrying
    them would mask credential problems. 5xx and 429 are retried with backoff.
    """
    signed = _authorization(method, host, path, payload, settings)
    parsed = urlparse(url)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if parsed.scheme == "https":
            connection = HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=30)
        else:
            connection = HTTPConnection(parsed.hostname, parsed.port or 80, timeout=30)
        try:
            connection.request(method, path, body=payload or None, headers=signed)
            response = connection.getresponse()
            status = response.status
            body = response.read()
            headers = {name.lower(): value for name, value in response.getheaders()}
        except (OSError, HTTPException) as exc:
            last_error = exc
            status = 0
            headers = {}
            body = b""
        finally:
            connection.close()
        transient = status == 0 or status == 429 or status >= 500
        if not transient or attempt >= retries:
            return status, headers, body
        time.sleep(retry_delay * (2 ** attempt))
    return 0, {}, b"" if last_error is None else str(last_error).encode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upload", "download", "describe-config", "validate-config"))
    parser.add_argument("--file", help="local file to upload or destination for download")
    parser.add_argument("--key", help="object key (defaults to file name under the prefix)")
    parser.add_argument("--dry-run", action="store_true", help="validate env and print a secret-free plan")
    parser.add_argument("--retries", type=int, default=2, help="transient retries (0-5, default 2)")
    parser.add_argument("--retry-delay", type=float, default=0.2, help="initial backoff seconds (default 0.2)")
    parser.add_argument("--expect-sha256", help="expected SHA-256 of a downloaded object")
    args = parser.parse_args(argv)
    if not 0 <= args.retries <= 5:
        raise SystemExit("--retries must be between 0 and 5")
    if not 0 <= args.retry_delay <= 5:
        raise SystemExit("--retry-delay must be between 0 and 5 seconds")
    if args.action == "validate-config":
        findings = _s3_findings()
        print(json.dumps({
            "status": "failed" if findings else "ok",
            "findings": findings,
            "values_exposed": False,
        }, sort_keys=True))
        return 1 if findings else 0
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
    host = urlparse(endpoint).netloc
    result: dict = {"action": args.action, "status": 0, "key": key,
                    "credentials_exposed": False}
    if args.action == "upload":
        payload = Path(args.file).read_bytes()
        status, response_headers, _ = _request(
            "PUT", url, payload, settings, host, path,
            retries=args.retries, retry_delay=args.retry_delay,
        )
        result["sha256"] = hashlib.sha256(payload).hexdigest()
    else:
        status, response_headers, payload = _request(
            "GET", url, b"", settings, host, path,
            retries=args.retries, retry_delay=args.retry_delay,
        )
        # A non-2xx body is an error document, not a backup. Write to a
        # temporary file and replace atomically only after full verification.
        if 200 <= status < 300:
            expected = (args.expect_sha256 or "").strip().lower()
            actual = hashlib.sha256(payload).hexdigest()
            if expected and actual != expected:
                result["status"] = status
                result["sha256_mismatch"] = True
                result["etag"] = response_headers.get("etag")
                result["version_id"] = response_headers.get("x-amz-version-id")
                print(json.dumps(result, sort_keys=True))
                return 1
            destination = Path(args.file)
            temporary = destination.with_name(destination.name + ".part")
            temporary.write_bytes(payload)
            os.replace(temporary, destination)
            result["sha256"] = actual
    result["status"] = status
    result["etag"] = response_headers.get("etag")
    result["version_id"] = response_headers.get("x-amz-version-id")
    print(json.dumps(result, sort_keys=True))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
