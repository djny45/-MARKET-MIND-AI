# OpenBB source import and CLI integration

MARKET-MIND-AI can vendor OpenBB's complete upstream source under `vendor/openbb`
without replacing its existing backend or research code.

## Import the full source

The full upstream repository is large. GitHub's file-by-file Contents API cannot
reliably copy an entire repository. Run the checked-in import helper locally
from the MARKET-MIND-AI root:

```bash
bash scripts/import-openbb.sh
```

It uses Git subtree to add the upstream `develop` branch at `vendor/openbb`,
refuses to overwrite an existing destination, and creates a local commit.
Review OpenBB's Apache-2.0 license and notices after importing. Keep upstream
changes isolated under `vendor/openbb`; do not overwrite MARKET-MIND-AI files.

After the subtree commit, run the import verifier:

```bash
bash scripts/verify-openbb-import.sh
```

The verifier checks expected source markers and Git tracking. It does not install
OpenBB or verify provider connectivity.

## CLI installation

**Use Python 3.11 or newer.** The current upstream OpenBB CLI v2 package declares
`requires-python = ">=3.11,<4"`; Python 3.10 will fail dependency installation.
See the [upstream CLI project metadata](https://github.com/openbq-org/OpenBB/blob/develop/cli/pyproject.toml).

Use the setup helper to install OpenBB CLI in a dedicated Python virtual
environment without changing MARKET-MIND-AI's backend dependencies:

```bash
bash scripts/setup-openbb-cli.sh
```

The script creates `.venv-openbb`, installs `openbb-cli`, and runs
`openbb --help` as a smoke check. It refuses to overwrite an existing
environment. On Windows, run it from Git Bash or Codespaces. If `python3` is
not on PATH, explicitly select a Python 3.11+ interpreter (for example, in Git Bash):

```bash
PYTHON_BIN=python bash scripts/setup-openbb-cli.sh
```

PowerShell users can activate the environment with:

```powershell
.\\.venv-openbb\\Scripts\\Activate.ps1
```

To install optional provider packages, activate that environment and install
only the provider integrations you need. Credentials and provider availability
depend on the chosen source.

OpenBB Platform V5 uses the `openbb-cli` 2.x package line. The CLI's interactive REPL is `openbb -i` (the default invocation is one-shot in V5). It is for trusted local use only;
the MARKET-MIND-AI web API does not proxy an interactive REPL.

## Backend adapter (implemented)

`backend/app/openbb_cli.py` supports only the informational actions `help`
and `version`. Help invokes the executable without a shell, applies an
8-second timeout, and caps output at 12,000 characters. If the combined stdout/stderr exceeds that limit, the adapter appends `… [output truncated]` so callers can distinguish complete output from a clipped response. Version is read from the installed
`openbb-cli` package metadata because OpenBB CLI v5 does not document a
`--version` flag. It does not accept raw command strings or arbitrary arguments.

**Execution is disabled by default.** For trusted local development, explicitly
set the environment variable:

```bash
OPENBB_CLI_ENABLED=true
```

The status endpoint reports both whether the CLI is installed and whether
execution is enabled. The frontend displays these as separate statuses. Unit
tests cover the opt-in gate and confirm a disabled request does not spawn a
subprocess. Do not enable this on a public deployment without
authentication, authorization, and rate limiting.

## Current terminal status

The React workspace contains an OpenBB panel, but it is a restricted
informational command panel—not a full interactive browser REPL. A browser
terminal requires a separate PTY/WebSocket bridge, authenticated sessions,
command allowlisting, lifecycle management, and resource/time limits. Do not
expose a raw server shell or unrestricted subprocess endpoint to the public
internet.

The full upstream source import is still a separate local Git-subtree step.
OpenBB is a research/data platform; it does not authorize live brokerage
execution. Keep data-source terms, credentials, and provenance visible.
