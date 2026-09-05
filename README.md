# ShiftZero HERO-002

**One sentence in. One verified robot mission out.**

Owner-private Judge Mode staging: https://shiftzero-hero-002.mingjen.chatgpt.site

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
.\.venv\Scripts\python.exe -m shiftzero.cli hero --provider fixture
.\.venv\Scripts\python.exe -m shiftzero.cli evaluate-scenarios
.\.venv\Scripts\python.exe -m shiftzero.cli build-evidence-bundle
```

The fixture provider is deterministic and is always labeled `fixture`; it is only for local
development. It is never presented as Nebius runtime evidence.

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

Official API references: [Token Factory function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling)
and the [Nebius Nemotron 3 Super guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-super-120B.md).

## Services

- `src/shiftzero`: frozen domain contracts, workflow, safety engine, simulator, evidence chain.
- `services/agent-api`: FastAPI entry point and deployment boundary.
- `services/simulator`: reference world and deterministic planner boundary.
- `adapters/reference-mqtt`: public simulator/MQTT contract.
- `adapters/real-agv`: hardware integration boundary, guarded by a signed compatibility result.
- `schemas`: checked-in JSON Schemas generated from the Pydantic contracts.
- `evidence`: verified run and compatibility outputs. Generated live evidence is ignored by Git.

Run the Agent API with:

```powershell
.\.venv\Scripts\python.exe -m uvicorn shiftzero.api:app --reload --port 8000
```

Run the Judge Mode website with:

```powershell
Set-Location apps\web
npm install
npm run dev
```

The judge-facing workflow is documented in `docs/JUDGE_MODE_RUNBOOK.md`. Offline evaluation
results are always marked as reference-simulator evidence; the UI keeps the live provider gate
visibly locked until real credentials produce a passing attestation.

## Scope

This release intentionally excludes a full WMS/ERP, mobile or voice clients, general-purpose
multi-agent orchestration, and proprietary customer adapters. See `docs/IP_BOUNDARY.md` and
`PRE_EXISTING_WORK.md` before publishing or importing older code.
