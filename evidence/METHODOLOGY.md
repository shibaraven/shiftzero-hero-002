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
- Every bundled Hero trace must contain all eight P0 tools. `get_mission_status` is sampled at the
  started, safe-stop and completed checkpoints so status is evidence, not merely a catalog entry.
- The route-only proof is recorded separately as `safety.route_proof`. Execution is authorized
  only after `safety.proof` adds a passing, hashed `approval_integrity` check binding the approval
  actor, expiry, proposal hash and mission goal. Replan proof repeats that integrity check.
- Immediately before the outcome is sealed, the controller calls the typed
  `get_operation_metrics` read tool. Its `operation-metrics-v1` result records one completed
  mission, duration, interventions, stop timing, model cost and final pose; the trace stores its
  arguments, result, hashes and measured tool latency.
- The fixture Compatibility preflight is explicitly unofficial. On 2026-09-06 the same six-variant
  matrix ran 20 times against live Token Factory/Nemotron: 120/120 runs completed and 360 model
  calls produced provider receipts. The aggregate report and every raw hash-chained trace are
  included in the Evidence Bundle; this remains simulator execution, not physical AGV evidence.
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

With `NEBIUS_API_KEY` supplied outside the repository, reproduce the official live gate with
`shiftzero compatibility --provider nebius --repetitions 20 --evidence-root
evidence/runs/live-compatibility --report evidence/compatibility/live-gate.json`, then rebuild the
bundle. The bundle validates the live report self-hash, run counts, trace chains, exact provider
and model, HTTP/tool-call receipts, positive token counts and request-ID uniqueness.

## Visual evidence

The private Judge Mode renders JSON evidence directly. Three checked-in PNG captures show the
COMPLETED mission, typed model-tool evidence and VERIFIED safety proof. Every capture visibly shows
`MOCK / FIXTURE` and the UTC timestamp bound to the verified Hero trace. The screenshot manifest
records capture time, dimensions and SHA-256; JSON/JSONL remains the primary machine-verifiable
evidence. The manifest classifies them as `preflight_fixture`, marks them ineligible for final
submission and requires replacement after the live gate. `validate-final-evidence` fails closed
until all three replacement images carry `LIVE / NEBIUS`, UTC timestamps, exact hashes and a real
provider receipt backed by `official_gate_passed=true`. The live gate now passes, but the final
correlated physical screenshots and AGV video remain absent.
