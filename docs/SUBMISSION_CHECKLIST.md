# Submission checklist

## Complete now

- [x] Repository and IP boundary documents.
- [x] Frozen hero scenario, schemas, state machine and safety rules.
- [x] Reference simulator and complete blockage/safe-stop/replan loop.
- [x] Nine-AGV A06/A07 Digital Twin Lab with 2D/isometric views, explicit pre-obstacle cloud
      disconnect, blockage injection, synthetic stop-latency pass/fail, route recovery, correlated
      event timeline and downloadable competition-simulation evidence.
- [x] Hash-bound A06/A07 reference run passes the no-hardware simulation path: 150 ms synthetic
      sensor-to-stationary, disconnected cloud route, changed route version, resume, completion and
      final pose under one correlation ID.
- [x] Physical field-test protocol, frozen evidence schema and fail-closed validator retained for
      optional future hardware claims; simulator files cannot be promoted into physical evidence.
- [x] Stateful Agent API and idempotent structured execution.
- [x] Tamper-evident trace and downloadable Evidence Bundle.
- [x] Machine-readable, hash-bound A01–A12 release report with evidence paths and explicit
      `external_evidence_required` status for physical/video/submission gates.
- [x] 100-scenario deterministic evaluation.
- [x] 20 consecutive complete Hero runs with a valid trace chain and route-version change.
- [x] 120-call fixture-provider compatibility preflight.
- [x] 120-run official live Nebius Compatibility Gate with 360 forced Nemotron tool calls,
      unique request IDs, 100% schema-valid results and a passing aggregate report.
- [x] Signed identity/RBAC, all-write idempotency/versioning, SQLite audit and exact replay.
- [x] Temporal collision, circular deadlock, sensor persistence and exact Digital Twin fields.
- [x] Separate Replan/Resume and fail-safe-only Override with append-only audit.
- [x] JSON+JSONL trace, all eight P0 tool spans, final pose, outcome metrics and three visibly
  timestamped `MOCK / FIXTURE` preflight screenshots.
- [x] `get_mission_status` trace evidence at started, safe-stop and completed checkpoints.
- [x] Execution and replan Safety Proofs contain a passing hashed `approval_integrity` check.
- [x] Fixture screenshots are machine-marked `preflight_fixture` and fail the final evidence gate.
- [x] Local production Judge Mode first-load report: 20 samples and p95 below 5,000 ms.
- [x] Explicitly scoped 400/450/500 pallets/day planning projection with 20 simulated days per
  load; assumptions are not represented as physical measurements.
- [x] Matched 20+20 Manual UI versus Agent Flow simulator baseline.
- [x] Judge Mode Run Hero, Architecture, Evidence and GitHub/source-gate entrances.
- [x] Devpost draft and three-minute video shot list.
- [x] Typed `get_operation_metrics` result is present in completed Hero traces and its JSON Schema
      is checked in.
- [x] No-hardware video plan reserves a continuous 65-second key-module simulation segment, a
      15-second opening and no more than 20 seconds for architecture within a 2:58 encoded target.
- [x] Devpost draft contains an explicit Existing work section linked to the detailed disclosure.
- [x] Resolved Python/npm inventory records exact versions, licenses and sources; Python
      verification dependencies are frozen.

## External prerequisites before final submission claims

- [x] Register and inject `NEBIUS_API_KEY` without committing it.
- [x] Record real forced Nemotron tool calls with provider/model/request receipts.
- [x] Pass the official Token Factory Compatibility Gate and archive its aggregate report plus
      120 raw hash-chained traces in the Evidence Bundle.
- [ ] Replace all three preflight screenshots with one correlated `LIVE / NEBIUS` + visibly labeled
      `DIGITAL TWIN / SIMULATION` capture set and make `validate-final-evidence` exit successfully.
- [x] Publish the Git repository and record an immutable verified revision URL.
- [x] Explicitly authorize public access for Judge Mode.
- [x] Verify Judge Mode without authentication and capture the deployment receipt.
- [ ] Record and upload the final demo video.

## Optional physical extension (not required by the official no-hardware path)

- [ ] Supply AGV protocol, site map, edge stop interface and safety-owner approval before any
      physical integration or physical-performance claim.
- [ ] If claiming real hardware, run the onsite A06/A07 protocol and make
      `validate-physical-evidence` pass with one synchronized continuous-video/telemetry/sensor/
      MQTT-or-VDA5050 evidence set.

## Final integrity checks

- [x] Public repository secret-pattern scan contains no detected API key, GitHub token or customer
      credential.
- [x] Evidence numbers in Devpost match the checked-in live runtime, scenario and KPI reports.
- [x] Simulator, live provider and optional physical evidence are visually and verbally
      distinguished.
- [x] Evidence Bundle SHA-256 matches `evidence/bundle-manifest.json`.
- [x] Current Judge Mode, public evidence artifacts and GitHub source links resolve without
      authentication; the final video link remains unavailable until recording.
