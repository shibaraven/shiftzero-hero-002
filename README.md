# ShiftZero HERO-002

**One sentence in. One verified robot mission out.**

Public Judge Mode: https://shiftzero-hero-002.mingjen.chatgpt.site

Public source: https://github.com/shibaraven/shiftzero-hero-002

ShiftZero HERO-002 is a proof-carrying mission-governance layer for warehouse robots. An
NVIDIA Nemotron model running on Nebius Token Factory may interpret intent and propose typed
actions, but it never drives an actuator. A deterministic controller, safety engine, explicit
human approval, and a local-stop-capable execution adapter authorize every physical action.

## Frozen hero scenario

Move pallet `P-104` from `INBOUND-01` to `RACK-A12` with `AGV-03`. During execution an aisle
blockage is injected. The robot must stop locally, obtain a newly verified equivalent route,
and complete the mission. The scenario definition is in `scenarios/hero.json`.

## Safety boundary

```text
Operator intent
  -> Nemotron typed proposal
  -> schema + live-entity + version validation
  -> deterministic planning and safety proof
  -> human approval bound to the proposal hash
  -> structured execution adapter
  -> local sensor-to-stop loop
```

The model can propose intent and tools. It cannot approve, dispatch, resume, or issue motor
commands. When the cloud or model is unavailable, the system does not create a new proposal.

## Quick start

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m shiftzero.cli export-schemas
.\.venv\Scripts\python.exe -m shiftzero.cli hero --provider fixture
.\.venv\Scripts\python.exe -m shiftzero.cli evaluate-scenarios
.\.venv\Scripts\python.exe -m shiftzero.cli verify-hero-reliability --runs 20
.\.venv\Scripts\python.exe -m shiftzero.cli fair-baseline --samples 20
.\.venv\Scripts\python.exe -m shiftzero.cli impact-load-model --sample-days 20
.\.venv\Scripts\python.exe -m shiftzero.cli build-license-inventory
.\.venv\Scripts\python.exe -m shiftzero.cli compatibility --provider fixture --repetitions 20
.\.venv\Scripts\python.exe -m shiftzero.cli build-hero-summary
.\.venv\Scripts\python.exe -m shiftzero.cli build-live-evidence-summary
.\.venv\Scripts\python.exe -m shiftzero.cli build-screenshot-manifest
.\.venv\Scripts\python.exe -m shiftzero.cli serverless-readiness --smoke-output tmp/serverless-smoke
.\.venv\Scripts\python.exe -m shiftzero.cli build-release-acceptance
.\.venv\Scripts\python.exe -m shiftzero.cli build-evidence-bundle
```

The fixture provider is deterministic and is always labeled `fixture`; it is only for local
development. It is never presented as Nebius runtime evidence.

The checked-in impact report evaluates 400, 450, and 500 pallets/day over 20 seeded simulated
days per load. It is explicitly a planning projection with declared cycle-time and operator-touch
assumptions—not physical throughput or observed labor savings. Completed Hero outcomes include
the final AGV node and `x`, `y`, and heading pose.

Every completed Hero trace contains all eight P0 tool spans. In particular,
`tool.get_mission_status` records the started, safe-stop, and completed checkpoints, and the typed
`tool.get_operation_metrics` result is validated by `operation-metrics.schema.json`. The final
Safety Proof includes a hashed `approval_integrity` result that binds the approval actor, expiry,
proposal hash, and mission goal before execution. The complete resolved Python/npm dependency
inventory is generated into `THIRD_PARTY_LICENSES.json`, with exact Python pins in
`requirements.lock` and the human-readable direct-dependency summary in
`THIRD_PARTY_NOTICES.md`.

## Real Token Factory verification

Export the environment variables described in `.env.example`, then run:

```powershell
$env:NEBIUS_API_KEY = "..."
.\.venv\Scripts\python.exe -m shiftzero.cli verify-token-factory
.\.venv\Scripts\python.exe -m shiftzero.cli hero --provider nebius
.\.venv\Scripts\python.exe -m shiftzero.cli compatibility --provider nebius --repetitions 20
```

The compatibility command executes six intent variants 20 times each. Only a report produced
with the real `nebius_token_factory` provider can set `official_gate_passed=true`. Missing
credentials fail closed; there is no silent mock fallback.

The checked-in aggregate live report passed on 2026-09-06: 120/120 simulator missions, 360/360
forced Nemotron tool calls with HTTP 200 and unique request IDs, 100% first/post-repair schema
validity, p95 intent-to-proposal 6.500 seconds, and zero reported failures. The raw live traces are
ignored as standalone working files but are hash-indexed inside the checked-in Evidence Bundle;
the API key is included in neither artifact.

`evidence/live-runtime-summary.json` aggregates the live request IDs and runtime metadata and
binds the prompt/tool schema to the tested commit. It also records 120/120 successful replans
(0.1215 ms median, 0.1427 ms p95) and a catalog-price KPI calculated from measured tokens:
$0.001925 median per simulator mission and $0.232801 for the complete gate. Cost is explicitly a
captured list-price estimate, not a billing invoice.

The checked-in screenshots are preflight-only `MOCK / FIXTURE` captures. They cannot be promoted
to final evidence. After the live gate and physical capture, validate their provider receipts,
hashes, UTC timestamps and visible `LIVE / NEBIUS` labels with:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli validate-final-evidence
```

See `docs/FINAL_EVIDENCE_CAPTURE.md` for the exact three-file replacement procedure.

## A06/A07 field-test rehearsal

Judge Mode **Evidence → Open field-test lab** contains a nine-AGV rehearsal inspired by the
provided dispatch simulator: switchable 2D/isometric views, speed controls, synthetic blockage,
local-stop timing presets, route recovery, event timeline, final pose, and downloadable rehearsal
JSON. Every screen and export says `SIMULATOR / PRE-PHYSICAL`; the export uses
`evidence_class=simulator_rehearsal`, is never final-submission eligible, and cannot pass A06/A07.

For the onsite closeout, collect one synchronized physical session following
`docs/A06_A07_FIELD_TEST_PROTOCOL.md`. Create a JSON file matching
`schemas/physical-field-evidence.schema.json`, then fail closed with:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli validate-physical-evidence `
  --input evidence/physical/field-session.json `
  --output evidence/physical/validation-report.json
```

The physical validator requires the correlated sensor, local stop, stationary, replan, resume and
completion events; a sensor-to-stop result no greater than 200 ms; changed route version; final
`x/y/heading`; four colocated source artifacts whose bytes match their declared SHA-256 hashes;
clock synchronization; cloud-disconnected stop proof; and a named safety-owner attestation.

`evidence/release-acceptance.json` evaluates the PDF's A01–A12 gates from checked-in evidence.
The current report passes A01–A05 and A08–A10, reports no software-evidence failures, and keeps
A06/A07/A11/A12 blocked on physical or owner-controlled artifacts.

Official API references: [Token Factory function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling)
and the [Nebius Nemotron 3 Super guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-super-120B.md).

## Services

- `src/shiftzero`: frozen domain contracts, workflow, safety engine, simulator, evidence chain.
- `services/agent-api`: FastAPI entry point and deployment boundary.
- `services/simulator`: reference world and deterministic planner boundary.
- `adapters/reference-mqtt`: public simulator/MQTT contract.
- `adapters/real-agv`: hardware integration boundary, guarded by a signed compatibility result.
- `schemas`: checked-in JSON Schemas generated from the Pydantic contracts.
- `evidence`: verified run and compatibility outputs. The aggregate live report and Evidence
  Bundle are checked in; standalone generated live traces are ignored by Git.

The deterministic evaluator has a separate non-interactive `Dockerfile.serverless`. Its checked-in
readiness report distinguishes a locally verified job artifact from an actual Nebius Serverless
deployment; `cloud_deployed` remains false until a successful cloud job receipt is captured.

All mutating Agent API calls require a signed bearer identity, idempotency key and expected version.
Stale writes return HTTP 409, verified-role violations return HTTP 403, and
Approve/Reject/Start/Stop/Replan/Resume/Override decisions are recorded in both the tamper-evident
trace and SQLite audit ledger. See `docs/AUTHORIZATION.md`; the checked-in `schemas/openapi.json` is
the frozen contract.

Run the Agent API with:

```powershell
$env:SHIFTZERO_AUTH_SECRET = "generate-at-least-32-random-characters"
.\.venv\Scripts\python.exe -m uvicorn shiftzero.api:app --reload --port 8000
```

Run the Judge Mode website with:

```powershell
Set-Location apps\web
npm install
npm run dev
```

The judge-facing workflow is documented in `docs/JUDGE_MODE_RUNBOOK.md`. Offline evaluation
results are always marked as reference-simulator evidence. The UI shows the passed live-provider
attestation separately while keeping the replay and current screenshots visibly `MOCK / FIXTURE`.

## Scope

This release intentionally excludes a full WMS/ERP, mobile or voice clients, general-purpose
multi-agent orchestration, and proprietary customer adapters. See `docs/IP_BOUNDARY.md` and
`PRE_EXISTING_WORK.md` before publishing or importing older code.
