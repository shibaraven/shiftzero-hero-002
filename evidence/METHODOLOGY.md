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
- The Compatibility preflight is explicitly unofficial. The official gate remains false until the
  same test matrix runs against live Token Factory/Nemotron and its raw request evidence is stored.

## Reproduction

Run `shiftzero export-schemas`, `shiftzero evaluate-scenarios`,
`shiftzero verify-hero-reliability --runs 20`, `shiftzero compatibility --provider fixture`, then
`shiftzero build-evidence-bundle`. The bundle manifest hashes every included byte.

## Visual evidence

The private Judge Mode renders the JSON evidence directly. Browser screenshots are not treated as
primary evidence because they are lossy and cannot be hash-verified; the site and downloadable
bundle remain the replayable source. Physical AGV video and live-provider screenshots are external
gates and are intentionally absent.
