# Devpost submission draft

## Project name

ShiftZero HERO-002

## Tagline

One sentence in. One verified robot mission out.

## Inspiration

Warehouse operators express goals in human language, while robots require exact, safe and
auditable commands. HERO-002 explores the missing layer between them: an AI can interpret and
propose, but deterministic policy, explicit human approval and a local safety controller retain
authority over physical action.

## What it does

An operator asks to move a pallet. The system resolves current world state, produces a typed
transport proposal, verifies it against frozen safety rules, binds a human approval to the exact
proposal, and dispatches a structured mission. In the hero scenario, an aisle becomes blocked
during execution. The robot-side adapter stops locally, a new route is planned and independently
verified, and the mission resumes with a tamper-evident evidence trail.

Judge Mode exposes the entire loop as a readable state sequence and provides an offline
Evidence Bundle. The deterministic suite covers 100 cases across nominal transport, aisle
blockage, low battery, occupied destinations, reservation conflicts and ambiguous intents.

## How we built it

- Python 3.12, Pydantic and FastAPI for typed domain contracts and the Agent API.
- A deterministic state machine and safety kernel separated from model output.
- A reference warehouse simulator plus a fail-closed real-AGV adapter boundary.
- OpenAI-compatible Token Factory integration configured for
  `nvidia/nemotron-3-super-120b-a12b` forced tool calling.
- Append-only JSONL evidence with a SHA-256 hash chain and reproducibility manifest.
- React/Next-compatible Judge Mode built with Sites, Tailwind and shadcn components.

## Challenges

The hardest design problem was preserving the usefulness of language-model reasoning without
letting probabilistic output become an actuation command. We treated typed tool output as an
untrusted proposal, versioned every live object it references, made approval content-addressed,
authenticated actor roles with short-lived signed tokens, persisted exact idempotency receipts,
and kept emergency stopping on the edge path.

## Accomplishments

- Complete simulator hero loop including obstacle detection, local safe stop and verified replan.
- Frozen schemas, transition rules and safety policy.
- Reproducible 100-scenario evaluation: 100/100 expected outcomes, zero observed safety
  violations, and 45/45 unsafe conditions rejected or safely handled.
- 120-call deterministic fixture preflight across six intent variants.
- Official live Token Factory Compatibility Gate: 120/120 simulator missions, 360/360 forced
  Nemotron tool calls with HTTP 200 and unique request IDs, 100% schema-valid output, p95
  intent-to-proposal 6.500 seconds and zero reported failures.
- A hash-bound live runtime report exposes the exact endpoint region, model, tested commit,
  prompt-contract hash, tool-schema hash, request IDs, per-call latency/tokens, and retry/repair
  counts without exposing an API key.
- Across those same 120 live-provider simulator runs, deterministic `replan_mission` succeeded
  120/120 times with 0.1215 ms median and 0.1427 ms p95 latency.
- Using measured token counts and the Token Factory model catalog snapshot ($0.30/M prompt,
  $0.90/M completion), the estimated median model cost was $0.001925 per mission and $0.232801
  for the 120-run gate. This is a reproducible list-price estimate, not a billing invoice.
- 20+20 matched Manual UI versus Agent Flow simulator baseline with method and sample size.
- Per-tool arguments/result hashes, latency/error fields and structured JSON replay artifacts.
- Credential-free owner-private Judge Mode staging and downloadable, hash-indexed evidence;
  public access remains an explicit release action.

The control-flow, safety and throughput results are scoped to the reference simulator. Model-call
compatibility results are from the live Nebius Token Factory provider; no physical AGV claim is
made.

## What we learned

Physical AI demos become more credible when the failure path is the centerpiece. The most useful
artifact is not a success animation; it is a linked record of what the system believed, which
rule authorized each transition, who approved it, and why it stopped.

We also learned that forced `tool_choice` is necessary but not sufficient. A provider can return
HTTP 200 and valid JSON while the arguments are still stale or semantically unsafe, so every
model result must pass schema, live-entity/version, and deterministic policy checks. Request IDs,
model name, region, prompt/schema hashes, latency, token counts, retries, repairs, and result hashes
must travel together; otherwise a polished UI cannot prove which runtime produced a decision.

Finally, cost needs the same claim discipline as safety. Token counts are measured, catalog prices
are time-stamped inputs, and their product is an estimate—not a cloud invoice. Separating those
three facts made the KPI useful without overstating what the evidence says.

## What's next

The live six-variant Compatibility Gate now passes. The project path is explicit:

1. **Project:** finish the competition release with a public Judge Mode, public source snapshot,
   Nebius deployment receipt, correlated physical-AGV trace, continuous 65-second physical clip,
   and three final `LIVE / NEBIUS` screenshots.
2. **IP:** preserve the pre-existing-work declaration, keep customer/OEM adapters outside the
   public core, and record the provenance and licenses of every shipped dependency.
3. **Product:** turn the frozen mission/safety contracts into a site-configurable governance layer
   with observability, role management, WMS integration, and deployment support.
4. **License/OEM:** keep the reference core Apache-2.0 and offer separately reviewed OEM protocol
   adapters, safety-controller integrations, support, and commercial deployment terms.

The physical phase requires an OEM protocol, MQTT or VDA 5050 gateway, PLC/edge stop contract,
mapped test area and safety-owner approval. Only after that integration will we record the
continuous physical segment and replace the fixture screenshots with one correlated evidence set.

## Existing work

Before 2026-08-26, HERO-001 had already established the concepts of deterministic WebMCP
end-to-end proof, a Digital Twin/AGV simulator, proposal-approval-blockage-replan flow, and a trace
and metrics foundation. Those concepts are prior work and are not presented as new hackathon
inventions.

During the HERO-002 competition period, this repository added the Nebius Token Factory/Nemotron
provider implementation, the six-variant Compatibility Gate, state-gated typed contracts,
three-layer validation, signed approval and idempotency controls, proof-carrying mission objects,
the reproducible 100-scenario suite, public-release-gated Judge Mode, and the hardware integration
boundary. Live-provider compatibility is now evidenced; Serverless deployment and physical claims
remain pending until their corresponding external evidence exists.

The detailed file-level declaration is maintained in `PRE_EXISTING_WORK.md`. The project owner
must confirm that declaration against the complete private history and sign/date it before final
submission; this draft does not impersonate that owner confirmation.

## Links to fill at submission time

- Judge Mode staging: `https://shiftzero-hero-002.mingjen.chatgpt.site` (owner-private until
  public access is explicitly approved)
- Source repository: `[ADD PUBLIC REPOSITORY URL]`
- Demo video: `[ADD VIDEO URL]`
- Live compatibility report: included in the downloadable Evidence Bundle; `[ADD PUBLIC ARTIFACT
  URL AT RELEASE]`
