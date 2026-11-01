# Vendored REA agent playbooks

Upstream source: https://github.com/morluto/rea

These four upstream skill instruction files are included under the upstream MIT license. They are available to relevant software-validation and research workers through the MARKET-MIND-AI skill catalog.

## Included playbooks

- `reverse-engineer-anything/` — evidence-led static investigation of a specifically selected application, package, or binary.
- `rea-analysis-optimization/` — analysis performance and resource optimization while preserving correctness.
- `rea-ci-tests-audit/` — CI, test-suite, fixture, and regression-gate audits.
- `rea-tool-design/` — investigation tool and evidence-contract design.

## Integration boundary

This import contains skill instructions, not the REA implementation. It does **not** install the REA CLI, register its MCP server, configure Ghidra/IDA/Hopper/Kuna, or make native analysis tools available. A skill's `requires_external_tools` catalog field is true; workers must check actual tool availability before attempting an REA operation. No unknown binary is to be executed, and targets must be explicitly selected by the user.

The REA skills are engineering guidance, not market signals or trading strategies. Worker profiles remain templates; adding a skill reference does not activate a worker or create a running agent. Select only the relevant skill for each task.

## License

See `UPSTREAM-LICENSE` for the upstream MIT license.
