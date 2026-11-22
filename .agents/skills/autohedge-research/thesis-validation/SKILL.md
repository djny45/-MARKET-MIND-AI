# AutoHedge-derived Research Thesis Validation Skill

**Upstream:** [The-Swarm-Corporation/AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge)  
**Adaptation:** Replaces the upstream execution-agent role with non-executing research validation.  
**Licence:** MIT; see `NOTICE.md` in this directory.

## Purpose
Challenge and validate a research thesis before it is included in a MARKET-MIND-AI report. It does not generate orders or execution parameters.

## Procedure
1. Restate the thesis as falsifiable claims with a defined instrument, horizon, and evidence window.
2. Check each claim against cited source material and supplied calculations.
3. Identify unsupported assumptions, contradictory evidence, stale inputs, look-ahead risks, and missing baselines.
4. Ask what evidence would disconfirm the thesis and whether alternative explanations fit the observations.
5. Check that reported metrics can be reproduced from the cited inputs.
6. Assign a validation status: supported, partially supported, unsupported, or not testable from available evidence.
7. Return specific research corrections to the Director profile; require human review for any change to a report or system configuration.

## Required output
- Claim-by-claim evidence matrix
- Contradictory or missing evidence
- Reproducibility and data-quality checks
- Validation status and rationale
- Human-review items

## Guardrails
- Never create, sign, route, or submit orders.
- Never output order type, quantity, entry, stop-loss, take-profit, or time-in-force instructions.
- Do not treat a thesis as a forecast or a guarantee.
- Keep validation separate from the original authoring agent to reduce confirmation bias.
