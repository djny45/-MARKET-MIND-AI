---
name: n8n-workflow-check
description: Build, repair or review importable n8n workflow JSON, with a reproducible test for valid input, invalid input and duplicate events. Use for n8n workflows, not general automation advice or unrelated code.
---

# n8n workflow review

Follow the portable source skill in `.agents/skills/n8n-workflow-check/SKILL.md` as the authoritative full procedure. This Claude Code entry exists so Claude Code discovers the skill in its native skill directory.

- Run the read-only checker at `.agents/skills/n8n-workflow-check/scripts/check_workflow.py`.
- Read the runtime procedure at `.agents/skills/n8n-workflow-check/references/runtime-check.md`.
- Keep workflow exports inactive and remove credential bindings from shareable examples.
- Never claim import or execution succeeded without verifying the target n8n instance.
- Require explicit human review before import. The repository importer must not activate or execute workflows.
- Never request or expose API keys or reviewer tokens in chat, prompts, source files, or workflow JSON.
