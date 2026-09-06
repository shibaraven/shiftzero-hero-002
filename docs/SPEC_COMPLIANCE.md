# SPEC V2.1 compliance ledger

This ledger separates local engineering completion from evidence that requires a credential,
physical hardware, public exposure, or a third-party submission action. `Complete` never means a
fixture result is equivalent to Nebius or physical evidence.

| Requirement | Status | Evidence or gate |
|---|---|---|
| Repository, hero scenario, IP boundary | Complete locally | `scenarios/hero.json`, `docs/IP_BOUNDARY.md`, `PRE_EXISTING_WORK.md` |
| Frozen schemas, state machine, safety rules | Complete locally | safety-v2 includes temporal collision, reservation availability, circular-wait deadlock and sensor persistence |
| Typed intent/proposal/recovery with no invented identifiers | Complete, including live provider | fixture ambiguity tests, `NEEDS_INPUT`, `RecoveryIntent`; live gate records 360 forced typed Nemotron calls |
| Deterministic simulator trust loop | Complete locally | Hero trace and 20-run reliability report |
| Human Approve/Reject/Stop/Resume/Override | Complete locally | signed actor identity, least-privilege roles, trace and SQLite audit; Override only terminates `FAILED_SAFE` |
| API idempotency and optimistic concurrency | Complete locally | every write requires key/version; SQLite exact-response receipts survive process replacement |
| Digital Twin core model | Complete locally | pose, pallet/location state, obstacle geometry/TTL, route windows, reservations and wait-for graph; completed outcome seals final `x/y/heading` |
| 100-case evaluation | Complete locally | differentiated S01-S06 results and method in Evidence Bundle |
| Evidence Bundle and reproducibility hashes | Complete for simulator + live provider | JSON+JSONL traces, 360 live provider receipts, tool latency/error/result hashes, visibly timestamped MOCK screenshots, outcome metrics and source/map/policy hashes; manifest sets `official_gate_passed=true` and keeps `final_release_ready=false` until physical capture |
| Complete P0 typed-tool trace | Complete locally | every bundled Hero trace contains snapshot, inspection, planning, proposal, approval, mission status, replan and metrics spans; status is read at started/safe-stop/completed checkpoints |
| Approval-integrity Safety Proof | Complete locally | execution and replan proofs contain a passing hashed check bound to proposal hash, actor, expiry and goal; bundle validation fails if it is absent |
| P0 `get_operation_metrics` typed tool | Complete locally | completed Hero and Agent API traces contain a schema-validated `tool.get_operation_metrics` span |
| Fair Manual vs Agent baseline | Complete locally | at least 20 matched simulator samples per flow; no physical savings claim |
| 400–500 pallets/day impact envelope | Complete as projection | seeded M/G/2 model, 20 simulated days at 400/450/500; assumptions explicit, no physical claim |
| Judge Mode load under 5 s | Complete locally | 20 browser timings against production build; method, raw samples, median and p95 recorded |
| Six variants x 20 Compatibility preflight | Complete locally, unofficial | fixture report remains `official_gate_passed=false` |
| Real Token Factory/Nemotron trace | Complete | 120 live runs, 360 HTTP-200 forced tool-call receipts, unique request IDs, exact provider/model identifiers and valid trace chains |
| Official Compatibility Gate | Complete | `official_gate_passed=true`; 120/120 complete, first/post-repair schema validity 100%, p95 6.500 s, no failures |
| Final three competition screenshots | Hardware-gated | current PNGs remain `preflight_fixture`; the live gate passes, but `validate-final-evidence` correctly rejects them until correlated physical results, `LIVE / NEBIUS` labels and replacement hashes exist |
| Serverless Jobs deployment | Account-gated | job contract/CLI complete; project, registry and storage target required |
| Real AGV adapter | Gate + hardware-gated | interface and handoff complete; OEM protocol/safety approval absent |
| Physical sensor-to-stop under 200 ms | Hardware-gated | simulator timings are never presented as physical timings |
| Public GitHub repository | Release authorization required | local Git complete; no remote configured |
| Anonymous public Judge Mode | Partially complete, release authorization required | local load/UX gate passes; deployed site remains owner-private |
| Physical demo video | Hardware/publication-gated | shot list complete; recording is not fabricated |
| Devpost submission | External action | draft/checklist complete; final URLs and submit action pending |
| Third-party dependency inventory | Complete locally | all resolved Python/npm packages have exact versions, license identifiers and sources; final legal review remains a release action |

The live runtime trace and official Compatibility Gate now satisfy the machine-verifiable A01/A02
provider requirements while remaining explicitly scoped to the reference simulator. A06, A07,
A09, A10, A11 and A12 still require their named hardware, public-access or submission evidence.
