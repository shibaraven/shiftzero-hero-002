# Evidence methodology

Every automated result declares its measurement scope. The 100-scenario suite and 20-run Hero
reliability gate use the deterministic fixture provider and the in-process reference simulator.
They demonstrate control flow, schema enforcement, safety gating, idempotency, replayability, and
tamper-evident evidence. They do not demonstrate live Nebius behavior or physical AGV timing.

## Calculation rules

- Scenario validity is `validated cases / 100`; unsafe-plan rejection recall is rejected or safely
  substituted unsafe cases divided by all labelled unsafe cases.
- Hero reliability passes only after at least 20 consecutive complete runs. Every run must contain
  the frozen state path, a route-version change after the blockage, and a valid SHA-256 trace chain.
- Stop latency in these reports is labelled `simulated_process`. No value is compared with the
  physical 200 ms sensor-to-stop requirement.
- Tool spans record tool name, arguments and result hashes, start/completion time, latency and
  error. Planner output records candidate count and estimated duration. Outcomes record duration,
  human interventions, cost, measurement scope, destination occupancy, and final `x/y/heading`
  pose.
- Immediately before the outcome is sealed, the controller calls the typed
  `get_operation_metrics` read tool. Its `operation-metrics-v1` result records one completed
  mission, duration, interventions, stop timing, model cost and final pose; the trace stores its
  arguments, result, hashes and measured tool latency.
- The Compatibility preflight is explicitly unofficial. The official gate remains false until the
  same test matrix runs against live Token Factory/Nemotron and its raw request evidence is stored.
- Judge Mode first-load evidence uses browser end-to-end wall time from navigation start until the
  page load state. The current report contains one new-tab navigation and 19 same-tab reloads of
  the local production build; median and interpolated p95 are compared with the 5,000 ms limit.
- The 400–500 pallets/day report is a seeded M/G/2 planning projection with 20 simulated days per
  load point. Its availability, dwell, buffer, operator-touch and fleet assumptions are inputs,
  not measurements. No projected labor saving or throughput is presented as a site observation.

## Reproduction

Run `shiftzero export-schemas`, `shiftzero evaluate-scenarios`,
`shiftzero verify-hero-reliability --runs 20`, `shiftzero compatibility --provider fixture`, then
`shiftzero fair-baseline --samples 20`, `shiftzero impact-load-model --sample-days 20`,
`shiftzero build-hero-summary`, `shiftzero build-screenshot-manifest`, and
`shiftzero build-evidence-bundle`. The bundle manifest hashes every included byte.

## Visual evidence

The private Judge Mode renders JSON evidence directly. Three checked-in PNG captures show the
COMPLETED mission, typed model-tool evidence and VERIFIED safety proof. Every capture visibly shows
`MOCK / FIXTURE` and the UTC timestamp bound to the verified Hero trace. The screenshot manifest
records capture time, dimensions and SHA-256; JSON/JSONL remains the primary machine-verifiable
evidence. The manifest classifies them as `preflight_fixture`, marks them ineligible for final
submission and requires replacement after the live gate. `validate-final-evidence` fails closed
until all three replacement images carry `LIVE / NEBIUS`, UTC timestamps, exact hashes and a real
provider receipt backed by `official_gate_passed=true`. Physical AGV video and live-provider
screenshots are external gates and remain absent.
