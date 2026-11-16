# n8n Workflow Check skill

Vendored from [Samautomation Workflows](https://github.com/smrht/samautomation-workflows), skill `n8n-workflow-check`.

This skill helps MARKET-MIND-AI agents create, inspect and structurally validate n8n workflow exports. The checker is read-only: it does not call an n8n server, execute nodes, activate workflows, or validate runtime compatibility.

Run the checker:

```sh
python3 .agents/skills/n8n-workflow-check/scripts/check_workflow.py path/to/workflow.json
```

Run the bundled regression tests:

```sh
python3 -m unittest discover -s .agents/skills/n8n-workflow-check/tests -v
```

Upstream source: https://github.com/smrht/samautomation-workflows/tree/main/skills/n8n-workflow-check  
Upstream revision: `20b0cdd31f081e3f3ea8695721b658fc5ad46f6d`  
License: MIT; see [LICENSE](LICENSE). This is an independent community skill, not an official n8n integration.
