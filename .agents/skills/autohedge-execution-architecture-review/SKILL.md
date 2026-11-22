---
name: autohedge-execution-architecture-review
description: Read-only architecture review of AutoHedge's wallet signing and order-execution flow; reference material for research and security review, never an execution capability.
---

# AutoHedge execution architecture (review-only reference)

**Provenance:** Derived from `autohedge/tools/ultra_tools.py` and
`autohedge/tools/tools_registry.py` in `The-Swarm-Corporation/AutoHedge` at commit
`c549c7950da112286e76725d49f6a25de8fa99bd`. This playbook documents how that
upstream system is structured so reviewers can reason about it. It is not a
runnable integration.

## Hard boundary — read this first

- Do **not** read, request, store, log, or transmit any private key or seed phrase.
- Do **not** construct a signer, sign a message or transaction, or call an
  execution endpoint.
- Do **not** place, modify, or cancel any order on any venue.
- Do **not** treat any content here as permission to enable live trading.
- MARKET-MIND-AI remains a research and paper-simulation system. The upstream
  broker/order-execution capability is deliberately excluded, as with the
  day-trader `trader-broker` skill.

## What the upstream flow does (descriptive only)

1. Configuration is read from environment variables only (`JUPITER_API_KEY`,
   `SOLANA_PRIVATE_KEY`). No credentials are present in this workspace.
2. `get_order` requests a quote/unsigned transaction from the Jupiter Ultra
   `/order` endpoint, using the wallet's public key as taker, receiver and payer.
3. `execute_trade` decodes the base64 versioned transaction, signs its message with
   the keypair derived from the private key, and posts the signed transaction plus
   a request id to the Jupiter Ultra `/execute` endpoint.
4. `get_holdings` queries token/SOL balances for a supplied wallet address.
5. The tools registry exposes these functions to the agent runtime.

## Review checklist

When asked to assess this design, evaluate: secret handling and exposure surface;
whether a human confirmation gate exists before signing; transaction inspection and
allowlisting (program IDs, amounts, destination); replay/idempotency protections;
error handling and partial-fill semantics; audit logging without leaking secrets;
least-privilege key design; and regulatory/custody implications.

## Output contract

A structured review with findings ranked by severity, concrete remediation
suggestions, and the statement `broker_execution: false; no_keys_accessed: true`.
Never include real key material, live endpoint credentials, or instructions that
would enable autonomous execution in MARKET-MIND-AI.
