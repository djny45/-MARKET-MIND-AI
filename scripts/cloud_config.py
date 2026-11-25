#!/usr/bin/env python3
"""Provider-independent cloud backup configuration and adapter wrapper.

The application does not depend on any one vendor: it speaks the S3-compatible
API through ``scripts/s3_offhost.py``. This module adds a vendor-neutral
environment contract (`MARKET_MIND_CLOUD_*`), validates it without printing any
value, and maps it to the existing adapter only at execution time.

Required:
  MARKET_MIND_CLOUD_ENDPOINT     HTTPS S3-compatible API root (no base path)
  MARKET_MIND_CLOUD_BUCKET       dedicated test bucket
  MARKET_MIND_CLOUD_REGION       provider region string
  MARKET_MIND_CLOUD_ACCESS_KEY   scoped access key id
  MARKET_MIND_CLOUD_SECRET_KEY   scoped secret access key
  MARKET_MIND_CLOUD_ENCRYPTION_KEY  base64 aes-256 key, OR
  MARKET_MIND_CLOUD_KEY_FILE     0600 file containing that key

Optional:
  MARKET_MIND_CLOUD_PROVIDER     descriptive label only, never a credential
  MARKET_MIND_CLOUD_PREFIX       object prefix (default market-mind/backups)

No command in this module prints a key, endpoint userinfo or mapped secret.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
S3_ADAPTER = SCRIPTS / "s3_offhost.py"

REQUIRED = (
    "MARKET_MIND_CLOUD_ENDPOINT",
    "MARKET_MIND_CLOUD_BUCKET",
    "MARKET_MIND_CLOUD_REGION",
    "MARKET_MIND_CLOUD_ACCESS_KEY",
    "MARKET_MIND_CLOUD_SECRET_KEY",
)
CLOUD_TO_S3 = {
    "MARKET_MIND_CLOUD_ENDPOINT": "MARKET_MIND_S3_ENDPOINT",
    "MARKET_MIND_CLOUD_BUCKET": "MARKET_MIND_S3_BUCKET",
    "MARKET_MIND_CLOUD_REGION": "MARKET_MIND_S3_REGION",
    "MARKET_MIND_CLOUD_ACCESS_KEY": "MARKET_MIND_S3_ACCESS_KEY",
    "MARKET_MIND_CLOUD_SECRET_KEY": "MARKET_MIND_S3_SECRET_KEY",
    "MARKET_MIND_CLOUD_PREFIX": "MARKET_MIND_S3_PREFIX",
}
BUCKET_RE = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
REGION_RE = re.compile(r"[a-z0-9-]{1,40}")


def _missing(environ: dict[str, str]) -> list[str]:
    return [key for key in REQUIRED if not environ.get(key, "").strip()]


def _key_source(environ: dict[str, str]) -> str | None:
    if environ.get("MARKET_MIND_CLOUD_ENCRYPTION_KEY", "").strip():
        return "env"
    if environ.get("MARKET_MIND_CLOUD_KEY_FILE", "").strip():
        return "file"
    return None


def _validate_key(environ: dict[str, str], findings: list[dict]) -> None:
    inline = environ.get("MARKET_MIND_CLOUD_ENCRYPTION_KEY", "").strip()
    key_file = environ.get("MARKET_MIND_CLOUD_KEY_FILE", "").strip()
    if inline and key_file:
        findings.append({
            "variable": "MARKET_MIND_CLOUD_ENCRYPTION_KEY/FILE",
            "issue": "conflicting_encryption_sources",
        })
        return
    if not inline and not key_file:
        findings.append({
            "variable": "MARKET_MIND_CLOUD_ENCRYPTION_KEY/FILE",
            "issue": "encryption_not_configured",
        })
        return
    if key_file:
        path = Path(key_file).expanduser()
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            if not path.is_file() or mode != 0o600:
                findings.append({"variable": "MARKET_MIND_CLOUD_KEY_FILE",
                                 "issue": "must_be_a_0600_file"})
        except OSError:
            findings.append({"variable": "MARKET_MIND_CLOUD_KEY_FILE",
                             "issue": "key_file_unreadable"})
        return
    try:
        raw = inline.encode("ascii")
        decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except (ValueError, UnicodeEncodeError, binascii.Error):
        findings.append({"variable": "MARKET_MIND_CLOUD_ENCRYPTION_KEY",
                         "issue": "must_be_base64_aes256_key"})
        return
    if len(decoded) != 32:
        findings.append({"variable": "MARKET_MIND_CLOUD_ENCRYPTION_KEY",
                         "issue": "must_be_32_bytes"})


def validate(environ: dict[str, str]) -> dict[str, object]:
    findings: list[dict] = []
    missing = _missing(environ)
    if missing:
        findings.append({"variable": "MARKET_MIND_CLOUD_*",
                         "issue": "missing_required_variables"})

    endpoint = environ.get("MARKET_MIND_CLOUD_ENDPOINT", "").strip().rstrip("/")
    if endpoint:
        try:
            parsed = urlsplit(endpoint)
        except ValueError:
            parsed = None
        if parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            findings.append({"variable": "MARKET_MIND_CLOUD_ENDPOINT",
                             "issue": "must_be_http_or_https_url"})
        else:
            if parsed.username or parsed.password:
                findings.append({"variable": "MARKET_MIND_CLOUD_ENDPOINT",
                                 "issue": "must_not_embed_credentials"})
            if parsed.path.strip("/"):
                findings.append({"variable": "MARKET_MIND_CLOUD_ENDPOINT",
                                 "issue": "must_not_include_base_path"})
            if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
                findings.append({"variable": "MARKET_MIND_CLOUD_ENDPOINT",
                                 "issue": "https_required_outside_loopback"})

    bucket = environ.get("MARKET_MIND_CLOUD_BUCKET", "").strip()
    if bucket and not BUCKET_RE.fullmatch(bucket):
        findings.append({"variable": "MARKET_MIND_CLOUD_BUCKET",
                         "issue": "invalid_bucket_name"})
    region = environ.get("MARKET_MIND_CLOUD_REGION", "").strip()
    if region and not REGION_RE.fullmatch(region):
        findings.append({"variable": "MARKET_MIND_CLOUD_REGION",
                         "issue": "invalid_region"})
    prefix = environ.get("MARKET_MIND_CLOUD_PREFIX", "").strip().strip("/")
    if ".." in prefix or len(prefix) > 200:
        findings.append({"variable": "MARKET_MIND_CLOUD_PREFIX",
                         "issue": "unsafe_prefix"})

    _validate_key(environ, findings)

    # Reuse the repository's fail-closed DR checks on the mapped adapter env.
    sys.path.insert(0, str(SCRIPTS))
    from dr_common import validate_dr_environment  # noqa: E402

    mapped = dict(environ)
    for cloud, s3 in CLOUD_TO_S3.items():
        value = environ.get(cloud, "").strip()
        if value:
            mapped[s3] = value
    adapter_findings = [
        item for item in validate_dr_environment(mapped)["findings"]
        if item["variable"].startswith("MARKET_MIND_S3_")
    ]
    findings.extend(adapter_findings)

    return {
        "status": "failed" if findings else "ok",
        "missing_variables": missing,
        "findings": findings,
        "encryption": {
            "configured": _key_source(environ) is not None and not any(
                item["variable"].startswith("MARKET_MIND_CLOUD_ENCRYPTION")
                for item in findings
            ),
            "source": _key_source(environ),
        },
        "values_exposed": False,
    }


def mapped_environ(environ: dict[str, str]) -> dict[str, str]:
    """Return an environment for the S3 adapter. Never logged or printed."""
    result = dict(environ)
    for cloud, s3 in CLOUD_TO_S3.items():
        value = environ.get(cloud, "").strip()
        if value:
            result[s3] = value
    if not environ.get("MARKET_MIND_CLOUD_PREFIX", "").strip():
        result.setdefault("MARKET_MIND_S3_PREFIX", "market-mind/backups")
    return result


def _adapter(args: list[str], environ: dict[str, str]) -> int:
    completed = subprocess.run(
        [sys.executable, str(S3_ADAPTER), *args],
        cwd=str(ROOT), env=mapped_environ(environ), capture_output=True, text=True,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=(
        "validate-config", "describe-config", "upload", "download",
    ))
    parser.add_argument("--file", help="local encrypted artifact path")
    parser.add_argument("--key", help="object key under the configured prefix")
    parser.add_argument("--expect-sha256", help="expected digest for downloads")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    environ = dict(os.environ)
    report = validate(environ)

    if args.command == "validate-config":
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "ok" else 1

    if report["status"] != "ok":
        print(json.dumps({"status": "failed", "findings": report["findings"],
                          "values_exposed": False}, sort_keys=True))
        return 1

    if args.command == "describe-config":
        print(json.dumps({
            "status": "ok",
            "endpoint": environ["MARKET_MIND_CLOUD_ENDPOINT"].strip().rstrip("/"),
            "bucket": environ["MARKET_MIND_CLOUD_BUCKET"].strip(),
            "region": environ["MARKET_MIND_CLOUD_REGION"].strip(),
            "prefix": environ.get("MARKET_MIND_CLOUD_PREFIX", "market-mind/backups").strip("/"),
            "provider_label": environ.get("MARKET_MIND_CLOUD_PROVIDER", "unspecified").strip(),
            "encryption": report["encryption"],
            "credentials_present": True,
            "credentials_exposed": False,
            "values_exposed": False,
            "dry_run": args.dry_run,
        }, sort_keys=True))
        return 0

    if not args.file:
        raise SystemExit("--file is required for upload/download")
    adapter_args = [args.command, "--file", args.file]
    if args.key:
        adapter_args += ["--key", args.key]
    if args.expect_sha256:
        adapter_args += ["--expect-sha256", args.expect_sha256]
    if args.dry_run:
        adapter_args += ["--dry-run"]
    return _adapter(adapter_args, environ)


if __name__ == "__main__":
    sys.exit(main())
