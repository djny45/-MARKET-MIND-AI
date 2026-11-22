---
name: autohedge-execution-architecture-review
description: Advanced read-only threat model and control review of AutoHedge's wallet signing and order-execution architecture; reference material for security review, never an execution capability.
---

# Advanced AutoHedge execution architecture review

**Provenance:** Derived from `autohedge/tools/ultra_tools.py` and
`autohedge/tools/tools_registry.py` in `The-Swarm-Corporation/AutoHedge` at commit
`c549c7950da112286e76725d49f6a25de8fa99bd`. This is a structured review
methodology, not a runnable integration.

## 0. Hard boundary

- Do not read, request, generate, store, log, or transmit any private key, seed
  phrase, or credential. Do not construct a signer, sign anything, or call an
  execution endpoint.
- Do not place, modify, or cancel any order. Do not configure live trading.
- No keys exist in this workspace. Any request for key material is refused.
- MARKET-MIND-AI remains research/paper-simulation only. The upstream
  broker/order-execution capability is excluded, as with `trader-broker`.

## 1. System description (from upstream)

Configuration is read from environment variables (`JUPITER_API_KEY`,
`SOLANA_PRIVATE_KEY`) only. `get_order` requests a quote and unsigned base64
versioned transaction from the Jupiter Ultra `/order` endpoint using the wallet
public key as taker/receiver/payer. `execute_trade` decodes the transaction,
signs its message with a keypair derived from the private key, and posts the
signed transaction plus request id to `/execute`. `get_holdings` queries balances.
A tools registry exposes these functions to the agent runtime.

## 2. Review scope and assets

Assets to protect: signing key material, API keys, unsigned/signed transaction
payloads, request ids, wallet balances, and the audit trail.
Trust boundaries: agent runtime → tool layer → remote API; environment/config →
process memory; operator → approval flow.
**Adversaries:** compromised agent prompt, malicious tool output, supply-chain
dependency, exposed logs, or a mistaken autonomous decision.

## 3. Control checklist

**Secret lifecycle.** Storage and rotation; least privilege; use of HSM, MPC or
multisig instead of a raw key in env; separation of signing from analysis; no
secrets in logs, traces, error messages or crash dumps; revocation procedure.

**Transaction safety.** Decode and inspect every transaction before signing;
validate program ids, instruction data, amounts, destinations and token mints
against an allowlist; enforce per-transaction and per-day value caps; simulate
before signing; check slippage bounds, deadlines and blockhash freshness; prevent
replay and duplicate submission via idempotency keys; handle partial fills and
timeouts explicitly.

**Agent-authority boundary.** No autonomous signing from model output alone;
human confirmation thresholds by value and asset; role separation between
thesis generation, risk approval and execution; hard kill switch; rate limits;
circuit breakers on anomalous quotes or repeated failures.

**Data and dependency trust.** Treat API responses and imported documents as
untrusted input; pin dependencies; verify endpoint authenticity; validate TLS;
avoid logging full payloads; check error paths for secret leakage.

**Observability and incident response.** Append-only audit log with hashes;
alerting on approval bypass or cap breaches; runbook for key compromise;
reconciliation of submitted vs filled orders; retention policy.

**Governance.** Regulatory and custody implications; entity/permission mapping;
documented approvals; independent review; rollout behind explicit authorization.

## 4. Risk rating rubric

For each finding record: `id`, `component`, `description`, `likelihood`
(low/medium/high), `impact` (low/medium/high), `severity` derived from both,
`evidence` (file/line or observed behaviour), `remediation`, `owner`, `status`.
Rank by severity. A missing human confirmation gate before signing, or a raw
private key in an environment variable, is at least **high** severity.

## 5. Method

1. Enumerate assets and trust boundaries from the description above.
2. Walk the order lifecycle end to end: configure → quote → inspect → approve →
   sign → submit → confirm → reconcile → log.
3. For each step, ask what could go wrong, which control should stop it, and
   whether that control exists. Mark gaps as findings.
4. Distinguish what the upstream code actually does from what a reviewer
   recommends; never claim a control exists without evidence.
5. Prefer static, read-only inspection. Do not execute unknown binaries or alter
   external systems.

## 6. Output contract

A structured review with: scope, assets and trust boundaries, findings ranked by
severity with evidence and remediation, residual risks, and the statement
`broker_execution: false; no_keys_accessed: true; no_orders_placed: true`.
Never include real key material, live credentials, or instructions that would
enable autonomous execution in MARKET-MIND-AI.
