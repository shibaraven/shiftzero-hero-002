# Implementation status - 2026-09-05

## Completed locally

- Git repository initialized with public/private IP boundaries and existing-work disclosure.
- Frozen hero scenario, typed JSON Schemas, state machine, tool catalog, and safety policy.
- OpenAI-compatible Nebius Token Factory provider for forced typed Nemotron tool calls.
- Deterministic simulator loop: observe, plan, propose, verify, approve, execute, block,
  local stop, replan, reverify, resume, complete.
- Append-only evidence trace with a verified SHA-256 hash chain.
- 120-run fixture preflight plus stale snapshot, invalid entity, timeout, HTTP 429, and duplicate
  dispatch controls.
- Compatibility attestation gate that prevents a fixture report from opening the real adapter.
- Stateful Agent API for intent, proposal, proof, approval, execution, stop, replan, trace, and
  metric inspection.
- Deterministic 100-scenario evaluation across six scenario families, with 100/100 validated
  outcomes, zero observed safety violations, and 45/45 unsafe conditions safely handled.
- Byte-reproducible, SHA-256-indexed Evidence Bundle.
- Interactive Judge Mode website with mission, architecture, and evidence views.
- Devpost draft, anonymous judge runbook, submission checklist, and three-minute video shot list.
- Owner-private Judge Mode deployment at `https://shiftzero-hero-002.mingjen.chatgpt.site`.

## Current external blockers

1. `NEBIUS_API_KEY` is not present in the execution environment. The real provider therefore
   fails closed, and the fixture preflight correctly records `official_gate_passed=false`.
2. No AGV/OEM protocol, broker credentials, PLC/edge stop interface, test map, or safety-owner
   approval has been supplied. Real hardware integration remains locked as required by the spec.

## Deferred external evidence

Run the following after setting the key:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli verify-token-factory --json
.\.venv\Scripts\python.exe -m shiftzero.cli compatibility --provider nebius --repetitions 20 --report evidence/compatibility/live-gate.json
```

Only if `live-gate.json` contains `official_gate_passed=true` should the site-approved real AGV
adapter implementation begin.
