"""Safe, non-interactive OpenBB CLI adapter for local research workflows.

This module intentionally does not expose a shell, arbitrary arguments, or an
interactive REPL over HTTP. Install OpenBB CLI separately (see docs/OPENBB-INTEGRATION.md).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal


OpenBBAction = Literal["help", "version"]


@dataclass(frozen=True)
class OpenBBCLIResult:
    available: bool
    action: str
    exit_code: int | None
    output: str
    error: str | None = None


_ALLOWED_ARGS: dict[OpenBBAction, tuple[str, ...]] = {
    "help": ("--help",),
    "version": ("--version",),
}
_MAX_OUTPUT_CHARS = 12_000
_TIMEOUT_SECONDS = 8


def openbb_cli_enabled() -> bool:
    """Require an explicit opt-in before starting the local CLI subprocess."""
    return os.getenv("OPENBB_CLI_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def run_openbb_cli(action: OpenBBAction) -> OpenBBCLIResult:
    """Run one fixed OpenBB CLI informational command without invoking a shell."""
    if action not in _ALLOWED_ARGS:
        raise ValueError("Unsupported OpenBB CLI action")

    if not openbb_cli_enabled():
        return OpenBBCLIResult(
            available=False,
            action=action,
            exit_code=None,
            output="",
            error="OpenBB CLI execution is disabled. Set OPENBB_CLI_ENABLED=true for trusted local use.",
        )

    executable = shutil.which("openbb")
    if executable is None:
        return OpenBBCLIResult(
            available=False,
            action=action,
            exit_code=None,
            output="",
            error="OpenBB CLI is not installed. See docs/OPENBB-INTEGRATION.md.",
        )

    try:
        completed = subprocess.run(
            [executable, *_ALLOWED_ARGS[action]],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
            shell=False,
            cwd=None,
        )
    except subprocess.TimeoutExpired:
        return OpenBBCLIResult(
            available=True,
            action=action,
            exit_code=None,
            output="",
            error=f"OpenBB CLI timed out after {_TIMEOUT_SECONDS} seconds.",
        )
    except OSError as exc:
        return OpenBBCLIResult(
            available=True,
            action=action,
            exit_code=None,
            output="",
            error=f"Could not start OpenBB CLI: {exc.__class__.__name__}",
        )

    output = (completed.stdout + completed.stderr).strip()
    return OpenBBCLIResult(
        available=True,
        action=action,
        exit_code=completed.returncode,
        output=output[:_MAX_OUTPUT_CHARS],
        error=None if completed.returncode == 0 else "OpenBB CLI returned a non-zero exit code.",
    )
