# SPEC V2.1 compliance ledger

This ledger separates local engineering completion from evidence that requires a credential,
physical hardware, public exposure, or a third-party submission action. `Complete` never means a
fixture result is equivalent to Nebius or physical evidence.

| Requirement | Status | Evidence or gate |
|---|---|---|
| Repository, hero scenario, IP boundary | Complete locally | `scenarios/hero.json`, `docs/IP_BOUNDARY.md`, `PRE_EXISTING_WORK.md` |
| Frozen schemas, state machine, safety rules | Complete locally | safety-v2 includes temporal collision, reservation availability, circular-wait deadlock and sensor persistence |
| Typed intent/proposal/recovery with no invented identifiers | Complete locally | fixture ambiguity tests, `NEEDS_INPUT`, `RecoveryIntent`; live behavior awaits key |
| Deterministic simulator trust loop | Complete locally | Hero trace and 20-run reliability report |
| Human Approve/Reject/Stop/Resume/Override | Complete locally | signed actor identity, least-privilege roles, trace and SQLite audit; Override only terminates `FAILED_SAFE` |
| API idempotency and optimistic concurrency | Complete locally | every write requires key/version; SQLite exact-response receipts survive process replacement |
| Digital Twin core model | Complete locally | pose, pallet/location state, obstacle geometry/TTL, route windows, reservations and wait-for graph; completed outcome seals final `x/y/heading` |
| 100-case evaluation | Complete locally | differentiated S01-S06 results and method in Evidence Bundle |
| Evidence Bundle and reproducibility hashes | Complete locally | JSON+JSONL traces, tool latency/error/result hashes, visibly timestamped MOCK screenshots, outcome metrics and source/map/policy hashes |
| Fair Manual vs Agent baseline | Complete locally | at least 20 matched simulator samples per flow; no physical savings claim |
| 400–500 pallets/day impact envelope | Complete as projection | seeded M/G/2 model, 20 simulated days at 400/450/500; assumptions explicit, no physical claim |
| Judge Mode load under 5 s | Complete locally | 20 browser timings against production build; method, raw samples, median and p95 recorded |
| Six variants x 20 Compatibility preflight | Complete locally, unofficial | fixture report remains `official_gate_passed=false` |
| Real Token Factory/Nemotron trace | Key-gated | `NEBIUS_API_KEY` plus provider receipt required |
| Official Compatibility Gate | Key-gated | must run 120 live calls; fixture cannot unlock it |
| Serverless Jobs deployment | Account-gated | job contract/CLI complete; project, registry and storage target required |
| Real AGV adapter | Gate + hardware-gated | interface and handoff complete; OEM protocol/safety approval absent |
| Physical sensor-to-stop under 200 ms | Hardware-gated | simulator timings are never presented as physical timings |
| Public GitHub repository | Release authorization required | local Git complete; no remote configured |
| Anonymous public Judge Mode | Partially complete, release authorization required | local load/UX gate passes; deployed site remains owner-private |
| Physical demo video | Hardware/publication-gated | shot list complete; recording is not fabricated |
| Devpost submission | External action | draft/checklist complete; final URLs and submit action pending |

The local column is complete only for the reference simulator and credential-free control plane.
It does not satisfy A01, A02, A06, A07, A09, A10, A11 or A12 without their named external evidence.
