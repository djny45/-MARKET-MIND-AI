# Claude Code skill adapter

The canonical skill, checker script, fixtures, references and regression tests are maintained under `.agents/skills/n8n-workflow-check/`. This small Claude Code adapter points to that portable source to avoid maintaining two copies of executable scripts and fixtures.

Run from the repository root:

```bash
python3 .agents/skills/n8n-workflow-check/scripts/check_workflow.py path/to/workflow.json
python3 -m unittest discover -s .agents/skills/n8n-workflow-check/tests -v
```
