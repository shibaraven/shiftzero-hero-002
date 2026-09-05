# Implementation status - 2026-09-05

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
- Devpost draft, anonymous judge runbook, submission checklist, and three-minute video shot list.
- Spec-aligned 2:58 video plan with a 15-second opening, at most 20 seconds of architecture and an
  uninterrupted 65-second physical segment; Devpost includes an explicit existing-work section.
- Complete resolved Python/npm dependency inventory with exact versions, license identifiers,
  source URLs and a frozen Python verification lock.
- Owner-private Judge Mode deployment at `https://shiftzero-hero-002.mingjen.chatgpt.site`.

## Current external blockers

1. `NEBIUS_API_KEY` is not present in the execution environment. The real provider therefore
   fails closed, and the fixture preflight correctly records `official_gate_passed=false`.
2. No AGV/OEM protocol, broker credentials, PLC/edge stop interface, test map, or safety-owner
   approval has been supplied. Real hardware integration remains locked as required by the spec.
3. The source repository has no authorized public remote, and Judge Mode is owner-private. Public
   release is a separate exposure decision rather than a local engineering task.
4. Physical video, anonymous-access verification, and Devpost submission require the final public
   URLs and hardware/test evidence.
5. The current three screenshots are preflight layout/evidence checks only. Final capture cannot
   pass until the live Compatibility Gate, real provider receipt and physical result exist.

## Deferred external evidence

Run the following after setting the key:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli verify-token-factory --json
.\.venv\Scripts\python.exe -m shiftzero.cli compatibility --provider nebius --repetitions 20 --report evidence/compatibility/live-gate.json
```

Only if `live-gate.json` contains `official_gate_passed=true` should the site-approved real AGV
adapter implementation begin.
