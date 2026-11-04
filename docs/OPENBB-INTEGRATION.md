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

## CLI installation

OpenBB CLI is a separate Python package. Install it in an isolated virtual
environment (Python 3.10+):

```bash
python -m venv .venv-openbb
# Linux/macOS
source .venv-openbb/bin/activate
# Windows PowerShell:
# .venv-openbb\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
python -m pip install openbb-cli openbb-oecd openbb-cboe
openbb --help
openbb -i
```

The CLI's interactive REPL is `openbb -i`. Provider packages and API
credentials are optional and depend on the research data sources you choose.

## Backend adapter (implemented)

`backend/app/openbb_cli.py` supports only the informational actions `help`
and `version`. It invokes the executable without a shell, applies an
8-second timeout, and caps output. It does not accept raw command strings or
arbitrary arguments.

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
