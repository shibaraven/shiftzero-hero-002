# Implementation status - 2026-09-06

## Completed locally

- Git repository initialized with public/private IP boundaries and existing-work disclosure.
- Frozen hero scenario, typed JSON Schemas, workflow-v2, tools-v3, and safety-v2 policy.
- OpenAI-compatible Nebius Token Factory provider for forced typed Nemotron tool calls.
- Deterministic simulator loop: observe, plan, propose, verify, approve, execute, block,
  local stop, typed RecoveryIntent, replan, reverify, separately authorized resume, complete.
- Append-only JSONL and structured JSON evidence with a verified SHA-256 hash chain and complete
  per-tool arguments/result hashes, latency and errors.
- 120-run fixture preflight plus stale snapshot, invalid entity, timeout, HTTP 429, and duplicate
  dispatch controls.
- Official 120-run live Nebius Token Factory Compatibility Gate: 120/120 complete, 360/360
  forced Nemotron tool calls returned HTTP 200 with unique provider request IDs, first/post-repair
  schema validity 100%, p95 intent-to-proposal 6.500 s, no retries, no repairs and no recorded
  failures. The aggregate report and all raw hash-chained traces are in the Evidence Bundle.
- Hash-bound live runtime metadata now identifies the exact endpoint region, model, tested commit,
  prompt-contract and tool-schema hashes, plus one judge-readable three-call receipt with request
  IDs, latency, token counts, retries, repairs, argument hashes and result hashes.
- Formal KPI aggregation over the same live-provider traces records 120/120 successful replans
  (0.1215 ms median, 0.1427 ms p95) and a measured-token × captured-catalog-price estimate of
  $0.001925 median per mission and $0.232801 for the 120-run gate; it is not an invoice.
- Compatibility attestation gate that prevents a fixture report from opening the real adapter.
- Stateful Agent API for intent, proposal, proof, approval, execution, stop, replan, resume,
  fail-safe override, trace and metric inspection. Signed bearer claims replace self-asserted
  roles; every write is versioned and stored in a SQLite exact-response idempotency ledger.
- Digital Twin pose, obstacle geometry/TTL, route-reservation time windows, vehicle compatibility,
  circular-wait deadlock detection, destination reachability and sensor persistence filtering.
- Differentiated 100-scenario evaluation across six scenario families. Nominal missions execute;
  static, temporary and sudden blockages follow distinct paths; unsafe cases are proof-gated; and
  ambiguous text goes through the real fixture parser without invented defaults.
- Independent 20-run Hero reliability gate with the complete state path, changed route version,
  and a verified SHA-256 trace chain required on every run.
- Matched 20-sample Manual UI versus Agent Flow simulator baseline, with no labor/time savings
  claim extrapolated to physical operations.
- Final completion evidence seals destination occupancy and AGV `x/y/heading` pose.
- Completed missions emit a typed, schema-validated `tool.get_operation_metrics` span carrying
  the per-mission sample size, completion, duration, intervention, stop, cost and final-pose KPIs.
- Every bundled Hero trace contains the complete eight-tool P0 catalog, including typed
  `get_mission_status` reads at started, safe-stop and completed checkpoints.
- Execution and equivalent-route replan proofs include a hashed `approval_integrity` result that
  verifies the proposal hash, goal, actor and expiry before motion is authorized.
- Seeded 400/450/500 pallets/day M/G/2 planning model with 20 simulated days per load, explicit
  assumptions, fleet-buffer recommendation, and no physical throughput or labor claim.
- Judge Mode local production-build load report with 20 browser samples and a 5,000 ms gate.
- Three SHA-256-indexed screenshots with a permanently visible `MOCK / FIXTURE` label and UTC
  trace timestamp.
- Fail-closed final screenshot validator. The checked-in fixture captures are explicitly
  `preflight_fixture`, never submission-eligible, and require replacement after the live gate.
- Byte-reproducible, SHA-256-indexed Evidence Bundle.
- Interactive Judge Mode website with Run Hero, Architecture, Evidence and GitHub/source-gate
  entrances, explicit MOCK labeling, final pose, load evidence, impact projection, typed
  model-tool and release-acceptance evidence.
- Evidence now links to an A06/A07 Field Test Lab with nine simulated AGVs, functional 2D and
  isometric views, speed/latency controls, manual blockage injection, local-stop/replan/resume
  timeline and downloadable rehearsal JSON. It is permanently marked `SIMULATOR / PRE-PHYSICAL`,
  `A06 NOT PASSED`, and `A07 NOT PASSED`.
- A strict `physical-field-evidence-v1` schema, field-test protocol, CLI validator and regression
  tests are complete. Simulator exports deliberately use a different, ineligible evidence class;
  only correlated onsite video/telemetry/sensor/protocol artifacts can pass the validator.
- A hash-bound A01–A12 release-acceptance report is generated from the underlying evidence and
  shown in Judge Mode. It passes 8/12, has no unresolved software-evidence failures, and identifies
  A06/A07/A11/A12 as external evidence gates rather than silently marking them complete.
- Devpost draft, anonymous judge runbook, submission checklist, and three-minute video shot list.
- Spec-aligned 2:58 video plan with a 15-second opening, at most 20 seconds of architecture and an
  uninterrupted 65-second physical segment; Devpost includes an explicit existing-work section.
- Complete resolved Python/npm dependency inventory with exact versions, license identifiers,
  source URLs and a frozen Python verification lock.
- Public Judge Mode deployment at `https://shiftzero-hero-002.mingjen.chatgpt.site`; v14 and its
  source SHA are captured in a deployment receipt, and four anonymous HTTP checks return 200.
- Public GitHub repository at `https://github.com/shibaraven/shiftzero-hero-002`; visibility,
  default branch, remote head, immutable commit URL and unauthenticated HTTP reachability are
  captured in `evidence/public-repository.json`.
- A dedicated non-interactive `Dockerfile.serverless` job artifact and fail-closed readiness
  report. Its 100-scenario local entrypoint passes 100/100 with zero observed safety violations.

## Current external blockers

1. No AGV/OEM protocol, broker credentials, PLC/edge stop interface, test map, or safety-owner
   approval has been supplied. Real hardware integration remains locked as required by the spec.
2. Physical video and Devpost submission require the final hardware/test evidence and video URL.
3. The current three screenshots are preflight layout/evidence checks only. The live Compatibility
   Gate and provider receipts now pass, but final capture still requires the correlated physical
   mission result and safety-owner review.
4. Nebius Serverless cloud execution requires an AI Cloud project ID, configured Nebius CLI,
   registry image URI, VM quota and a successful job receipt. None is present on this machine;
   the Token Factory inference key does not supply those project resources.
5. The project owner must verify the private-history disclosure and sign/date
   `PRE_EXISTING_WORK.md`; automation cannot truthfully make that attestation for the owner.

## Live gate result and next external gate

The completed command was:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli verify-token-factory --json
.\.venv\Scripts\python.exe -m shiftzero.cli compatibility --provider nebius --repetitions 20 --evidence-root evidence/runs/live-compatibility --report evidence/compatibility/live-gate.json
```

`live-gate.json` contains `official_gate_passed=true`. Real AGV adapter implementation may begin
only after the site supplies the OEM protocol, mapped test area, edge-stop interface and explicit
safety-owner approval. The API key remains outside Git and the Evidence Bundle.
