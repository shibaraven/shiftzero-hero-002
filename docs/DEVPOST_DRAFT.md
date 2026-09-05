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
and kept emergency stopping on the edge path.

## Accomplishments

- Complete simulator hero loop including obstacle detection, local safe stop and verified replan.
- Frozen schemas, transition rules and safety policy.
- Reproducible 100-scenario evaluation: 100/100 expected outcomes, zero observed safety
  violations, and 45/45 unsafe conditions rejected or safely handled.
- 120-call deterministic fixture preflight across six intent variants.
- Credential-free public Judge Mode and downloadable, hash-indexed evidence.

These results are explicitly scoped to the reference simulator and fixture provider.

## What we learned

Physical AI demos become more credible when the failure path is the centerpiece. The most useful
artifact is not a success animation; it is a linked record of what the system believed, which
rule authorized each transition, who approved it, and why it stopped.

## What's next

After Token Factory credentials are registered, run the forced live tool-call check and the
official six-variant Compatibility Gate. Only a passing live report can unlock site-approved AGV
transport work. The next physical phase requires an OEM protocol, MQTT or VDA 5050 gateway,
PLC/edge stop contract, mapped test area and safety-owner approval.

## Links to fill at submission time

- Judge Mode: `[ADD DEPLOYED URL]`
- Source repository: `[ADD PUBLIC REPOSITORY URL]`
- Demo video: `[ADD VIDEO URL]`
- Live compatibility report: `[ADD ONLY AFTER OFFICIAL GATE PASSES]`
