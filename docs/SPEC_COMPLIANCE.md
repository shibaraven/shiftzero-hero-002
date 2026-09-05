# SPEC V2.1 compliance ledger

This ledger separates local engineering completion from evidence that requires a credential,
physical hardware, public exposure, or a third-party submission action. `Complete` never means a
fixture result is equivalent to Nebius or physical evidence.

| Requirement | Status | Evidence or gate |
|---|---|---|
| Repository, hero scenario, IP boundary | Complete locally | `scenarios/hero.json`, `docs/IP_BOUNDARY.md`, `PRE_EXISTING_WORK.md` |
| Frozen schemas, state machine, safety rules | Complete locally | `schemas/`, `docs/SAFETY_RULES.md` |
| Typed intent/proposal with no invented identifiers | Complete locally | fixture ambiguity tests and `NEEDS_INPUT`; live behavior awaits key |
| Deterministic simulator trust loop | Complete locally | Hero trace and 20-run reliability report |
| Human Approve/Reject and explicit Stop | Complete locally | Agent API/OpenAPI, role gates, idempotent audit events, Judge replay controls |
| API idempotency and optimistic concurrency | Complete locally | repeated request and stale-version tests |
| 100-case evaluation | Complete locally | differentiated S01-S06 results and method in Evidence Bundle |
| Evidence Bundle and reproducibility hashes | Complete locally | bundle manifest, trace chains, source/map/policy hashes |
| Six variants x 20 Compatibility preflight | Complete locally, unofficial | fixture report remains `official_gate_passed=false` |
| Real Token Factory/Nemotron trace | Key-gated | `NEBIUS_API_KEY` plus provider receipt required |
| Official Compatibility Gate | Key-gated | must run 120 live calls; fixture cannot unlock it |
| Serverless Jobs deployment | Account-gated | job contract/CLI complete; project, registry and storage target required |
| Real AGV adapter | Gate + hardware-gated | interface and handoff complete; OEM protocol/safety approval absent |
| Physical sensor-to-stop under 200 ms | Hardware-gated | simulator timings are never presented as physical timings |
| Public GitHub repository | Release authorization required | local Git complete; no remote configured |
| Anonymous public Judge Mode | Release authorization required | owner-private deployment exists |
| Physical demo video | Hardware/publication-gated | shot list complete; recording is not fabricated |
| Devpost submission | External action | draft/checklist complete; final URLs and submit action pending |
