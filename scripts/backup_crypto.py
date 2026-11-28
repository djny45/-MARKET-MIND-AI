#!/usr/bin/env python3
"""Authenticated encryption for research-database backups.

Uses AES-256-GCM from the already pinned ``cryptography`` runtime dependency.
The key is read only from the environment or a 0600 key file and is never
printed, logged or written into a manifest. The AES-GCM tag and a plaintext
SHA-256 digest are both verified before a decrypted file is accepted.

Commands:
  encrypt --file <backup.db> --output <backup.db.enc>
  decrypt --file <backup.db.enc> --output <restore.db>
  verify  --file <backup.db.enc>

Exit 0 means the operation and integrity checks succeeded.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as exc:  # pragma: no cover - dependency is pinned in requirements
    raise SystemExit(f"missing required cryptography dependency: {exc}") from exc

MAGIC = b"MMBK-GCM"
VERSION = 1
NONCE_BYTES = 12
KEY_BYTES = 32
HEADER_BYTES = len(MAGIC) + 1 + NONCE_BYTES + 32


def _key(environ: dict[str, str]) -> bytes:
    inline = environ.get("MARKET_MIND_CLOUD_ENCRYPTION_KEY", "").strip()
    path_text = environ.get("MARKET_MIND_CLOUD_KEY_FILE", "").strip()
    if inline and path_text:
        raise SystemExit("conflicting_encryption_sources (values are never printed)")
    if not inline and not path_text:
        raise SystemExit(
            "MARKET_MIND_CLOUD_ENCRYPTION_KEY or MARKET_MIND_CLOUD_KEY_FILE is required "
            "(values are never printed)"
        )
    if path_text:
        path = Path(path_text).expanduser()
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            if not path.is_file() or mode != 0o600:
                raise SystemExit("MARKET_MIND_CLOUD_KEY_FILE must be a 0600 file")
            inline = path.read_text(encoding="ascii").strip().splitlines()[0].strip()
        except (OSError, UnicodeError, IndexError) as exc:
            raise SystemExit(f"MARKET_MIND_CLOUD_KEY_FILE unreadable: {type(exc).__name__}") from exc
    try:
        raw = inline.encode("ascii")
        decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise SystemExit(f"invalid base64 encryption key: {type(exc).__name__}") from exc
    if len(decoded) != KEY_BYTES:
        raise SystemExit("encryption key must decode to 32 bytes")
    return decoded


def _header(nonce: bytes, plaintext_digest: bytes) -> bytes:
    return MAGIC + bytes([VERSION]) + nonce + plaintext_digest


def _parse_header(payload: bytes) -> tuple[bytes, bytes, bytes]:
    if len(payload) < HEADER_BYTES or payload[:len(MAGIC)] != MAGIC:
        raise ValueError("invalid_encrypted_backup_header")
    version = payload[len(MAGIC)]
    if version != VERSION:
        raise ValueError("unsupported_encrypted_backup_version")
    nonce = payload[len(MAGIC) + 1:len(MAGIC) + 1 + NONCE_BYTES]
    digest = payload[len(MAGIC) + 1 + NONCE_BYTES:HEADER_BYTES]
    return nonce, digest, payload[HEADER_BYTES:]


def _open(payload: bytes, key: bytes) -> bytes:
    nonce, digest, ciphertext = _parse_header(payload)
    header = payload[:HEADER_BYTES]
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, header)
    if hashlib.sha256(plaintext).digest() != digest:
        raise ValueError("plaintext_sha256_mismatch")
    return plaintext


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(payload)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("encrypt", "decrypt", "verify"))
    parser.add_argument("--file", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    source = Path(args.file)
    if not source.is_file():
        print(json.dumps({"status": "missing_file", "values_exposed": False}))
        return 1
    if args.command in ("encrypt", "decrypt") and not args.output:
        raise SystemExit("--output is required for encrypt/decrypt")

    try:
        key = _key(dict(os.environ))
        if args.command == "encrypt":
            plaintext = source.read_bytes()
            digest = hashlib.sha256(plaintext).digest()
            nonce = os.urandom(NONCE_BYTES)
            header = _header(nonce, digest)
            encrypted = header + AESGCM(key).encrypt(nonce, plaintext, header)
            assert args.output is not None
            _atomic_write(Path(args.output), encrypted)
            result = {
                "status": "encrypted",
                "algorithm": "AES-256-GCM",
                "plaintext_sha256": digest.hex(),
                "encrypted_bytes": len(encrypted),
                "output": str(args.output),
                "integrity_verified": True,
            }
        else:
            plaintext = _open(source.read_bytes(), key)
            digest = hashlib.sha256(plaintext).hexdigest()
            if args.command == "decrypt":
                assert args.output is not None
                _atomic_write(Path(args.output), plaintext)
                result = {
                    "status": "decrypted",
                    "algorithm": "AES-256-GCM",
                    "sha256": digest,
                    "output": str(args.output),
                    "integrity_verified": True,
                }
            else:
                result = {
                    "status": "verified",
                    "algorithm": "AES-256-GCM",
                    "sha256": digest,
                    "integrity_verified": True,
                }
    except (InvalidTag, ValueError) as exc:
        print(json.dumps({"status": "integrity_failed", "reason": str(exc),
                          "values_exposed": False}))
        return 1
    except OSError as exc:
        print(json.dumps({"status": "io_failed", "reason": type(exc).__name__,
                          "values_exposed": False}))
        return 1

    result["values_exposed"] = False
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
