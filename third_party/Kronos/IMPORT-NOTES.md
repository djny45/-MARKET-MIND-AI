# Kronos vendored source

This directory is a source-preserving vendor import of
[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos).

- Upstream project: Kronos — A Foundation Model for the Language of Financial Markets
- Upstream repository: https://github.com/shiyu-coder/Kronos
- Imported upstream commit: `67b630e67f6a18c9e9be918d9b4337c960db1e9a`
- Upstream branch at import: `master`
- Upstream licence: MIT; see [LICENSE](LICENSE)
- Import method: Git subtree snapshot, preserving the upstream directory structure
- Upstream tree entries at import: 107 (including directories)

## Important boundaries

- This is vendored source code, not a configured or running model service.
- The upstream repository does not contain the pretrained model checkpoint weights; obtain them separately from the model publisher and review their terms before use.
- Upstream examples, training scripts, fine-tuning utilities, and web UI are retained as source. They are not imported into MARKET-MIND-AI's runtime, installed, or executed by this project.
- Do not connect this vendor directory to broker APIs, order routing, or automated trading. Any later evaluation must be an isolated historical-data research experiment with clear validation, leakage controls, and documented limitations.
- Treat upstream code and dependencies as third-party software: review and pin dependencies before any optional local setup.

## Updating

The import workflow is pinned to the upstream commit above. Review upstream changes and update the pinned commit deliberately; do not silently track the upstream default branch.
