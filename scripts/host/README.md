# Systemd units for the MARKET-MIND-AI private research stack
#
# These are HOST integration artifacts. They are provided so an operator with
# root on a real host can install persistence in one step. They are not
# installed by this repository and no privileged command is run automatically.
#
# Prerequisites on the target host:
#   * systemd present (not true in the current unprivileged container)
#   * the app venv built:  cd backend && python3 -m venv ../.venvs/backend && ...
#   * /home/jovyan/.market-mind-ops/private.env created with mode 0600
#
# Files:
#   market-mind-stack.service        the stack (bootstrap -> loop -> services)
#   market-mind-stack.cron           cron fallback if systemd is unavailable
#
# Install:
#   sudo cp scripts/host/market-mind-stack.service /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now market-mind-stack.service
#   systemctl status market-mind-stack.service
#
# Verify after install:
#   /home/jovyan/.market-mind-ops/supervision/status.py
#   sudo systemctl is-enabled market-mind-stack.service   # -> enabled
#
# Remove:
#   sudo systemctl disable --now market-mind-stack.service
#   sudo rm /etc/systemd/system/market-mind-stack.service
