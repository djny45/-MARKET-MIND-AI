"""Safe, non-interactive OpenBB CLI adapter for local research workflows.

This module intentionally does not expose a shell, arbitrary arguments, or an
interactive REPL over HTTP. Install OpenBB CLI separately (see docs/OPENBB-INTEGRATION.md).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from threading import BoundedSemaphore, Event, Thread
import time
from pathlib import Path
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
}
_MAX_OUTPUT_CHARS = 12_000
_OUTPUT_TRUNCATION_MARKER = "\n… [output truncated]"
_TIMEOUT_SECONDS = 8
# One help subprocess per backend worker at a time. This prevents bursts of
# requests from spawning unbounded child processes in a single worker.
_HELP_RUN_SEMAPHORE = BoundedSemaphore(1)


def _cap_output(output: str) -> str:
    """Keep CLI output bounded and make truncation visible to the caller."""
    if len(output) <= _MAX_OUTPUT_CHARS:
        return output
    marker = _OUTPUT_TRUNCATION_MARKER
    return output[: _MAX_OUTPUT_CHARS - len(marker)] + marker


def openbb_cli_enabled() -> bool:
    """Require an explicit opt-in before starting the local CLI subprocess."""
    return os.getenv("OPENBB_CLI_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def run_openbb_cli(action: OpenBBAction) -> OpenBBCLIResult:
    """Run a fixed informational action without exposing arbitrary CLI arguments."""
    if action not in {"help", "version"}:
        raise ValueError("Unsupported OpenBB CLI action")

    if not openbb_cli_enabled():
        return OpenBBCLIResult(
            available=shutil.which("openbb") is not None,
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

    # OpenBB CLI v5 does not document a --version flag. Query package
    # metadata with the Python interpreter beside the resolved executable,
    # which keeps the lookup inside the CLI's dedicated virtual environment.
    if action == "version":
        python_name = "python.exe" if os.name == "nt" else "python"
        python_executable = Path(executable).resolve().parent / python_name
        if not python_executable.is_file():
            return OpenBBCLIResult(
                available=True,
                action=action,
                exit_code=None,
                output="",
                error="Could not locate the Python interpreter beside the OpenBB executable.",
            )
        version_code = (
            "import importlib.metadata as m; "
            "print(m.version('openbb-cli'))"
        )
        try:
            completed = subprocess.run(
                [str(python_executable), "-c", version_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False,
                timeout=5,
                text=True,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return OpenBBCLIResult(
                available=True,
                action=action,
                exit_code=None,
                output="",
                error=f"Could not read OpenBB CLI metadata: {exc.__class__.__name__}",
            )
        output = _cap_output(completed.stdout.strip())
        if completed.returncode != 0:
            return OpenBBCLIResult(
                available=True,
                action=action,
                exit_code=completed.returncode,
                output=output,
                error="OpenBB CLI package metadata was not found in its Python environment.",
            )
        return OpenBBCLIResult(
            available=True,
            action=action,
            exit_code=0,
            output=f"OpenBB CLI version {output}",
        )

    if not _HELP_RUN_SEMAPHORE.acquire(blocking=False):
        return OpenBBCLIResult(
            available=True,
            action=action,
            exit_code=None,
            output="",
            error="OpenBB CLI is busy; retry after the current informational command finishes.",
        )

    process = None
    captured = bytearray()
    output_limit_reached = Event()
    reader_done = Event()

    def _read_bounded_output() -> None:
        try:
            assert process is not None and process.stdout is not None
            while True:
                chunk = process.stdout.read(1024)
                if not chunk:
                    break
                remaining = _MAX_OUTPUT_CHARS + 1 - len(captured)
                if remaining > 0:
                    captured.extend(chunk[:remaining])
                if len(chunk) > remaining or len(captured) > _MAX_OUTPUT_CHARS:
                    output_limit_reached.set()
                    process.terminate()
                    break
        finally:
            reader_done.set()

    try:
        try:
            process = subprocess.Popen(
                [executable, *_ALLOWED_ARGS[action]],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False,
                cwd=None,
            )
        except OSError as exc:
            return OpenBBCLIResult(
                available=True,
                action=action,
                exit_code=None,
                output="",
                error=f"Could not start OpenBB CLI: {exc.__class__.__name__}",
            )

        reader = Thread(target=_read_bounded_output, daemon=True)
        reader.start()
        deadline = time.monotonic() + _TIMEOUT_SECONDS
        while process.poll() is None and time.monotonic() < deadline:
            if output_limit_reached.is_set():
                break
            time.sleep(0.025)

        timed_out = process.poll() is None and not output_limit_reached.is_set()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        reader.join(timeout=1)

        output = captured.decode("utf-8", errors="replace").strip()
        if output_limit_reached.is_set():
            output = _cap_output(output)
            return OpenBBCLIResult(
                available=True,
                action=action,
                exit_code=process.returncode,
                output=output,
                error="OpenBB CLI output exceeded the configured limit; process terminated.",
            )
        if timed_out:
            return OpenBBCLIResult(
                available=True,
                action=action,
                exit_code=None,
                output=output,
                error=f"OpenBB CLI timed out after {_TIMEOUT_SECONDS} seconds.",
            )
        return OpenBBCLIResult(
            available=True,
            action=action,
            exit_code=process.returncode,
            output=_cap_output(output),
            error=None if process.returncode == 0 else "OpenBB CLI returned a non-zero exit code.",
        )
    finally:
        _HELP_RUN_SEMAPHORE.release()
