# OpenCode setup — GitHub Codespaces

## 1. Open a cloud workspace
1. Open https://github.com/djny45/-MARKET-MIND-AI
2. Select the repository's `mece/opencode-bootstrap` branch.
3. Choose **Code → Codespaces → Create codespace on mece/opencode-bootstrap**.
4. Wait for the terminal to become available.

## 2. Check whether OpenCode exists
Run:
```bash
command -v opencode >/dev/null && opencode --version || echo "OpenCode is not installed"
```

## 3. Install if missing
Use the official OpenCode installation instructions at https://opencode.ai/docs/ (or https://opencode.ai). Review the installer before running it. Do not use an unofficial binary or paste secrets into shell commands.

## 4. Connect user-owned free authentication
Start OpenCode:
```bash
opencode
```
Use `/connect` and choose a provider/account you personally control, such as an eligible OpenCode Zen/Go account or a provider with a free tier. Check the provider's current quota and terms in its own UI. Do not assume unlimited free usage. Do not share API keys in chat, commits, task reports, or screenshots.

If you do not have a free provider account, stop here and choose one before launching agents. The MECE audit must not silently switch to a paid provider.

## 5. Verify the runtime
```bash
opencode --version
opencode models
```
Confirm a model is available and selected. Keep provider credentials in OpenCode's supported local credential store or Codespaces secrets; never commit them.

## 6. Run the audit wave
From the repository root:
```bash
for cell in BACKEND FRONTEND DATA SECURITY QUALITY OPERATIONS; do
  mkdir -p ".mece/cells/$cell"
  opencode run --dir . "$(cat ".mece/cells/$cell/TASK.md")"
done
```
Run sequentially initially to avoid resource contention. Each task instructs OpenCode to write its report to the cell's REPORT.md. Review each report before continuing if it requests changes or access to secrets.

## 7. Commit reports
Inspect the diff and secret scan before committing:
```bash
git status --short
git diff --check
git diff
```
Do not commit credentials, environment files, database dumps, generated datasets, or private logs. Commit only the six audit reports and the parent synthesis after review.

## Cost and safety
Codespaces usage may be chargeable after included quotas. OpenCode model usage may also have quotas or charges depending on the provider/account. Check both account dashboards first. No background fleet or remote agent is started by this setup guide.
