# Final evidence capture gate

The three screenshots currently stored in `evidence/screenshots/` are local preflight captures.
They are visibly labeled `MOCK / FIXTURE`, have timestamps and hashes, and are useful for layout
and reproducibility checks. They are not eligible as A01/final screenshot evidence.

## Prerequisites

As of 2026-09-06, prerequisites 1 and 2 pass. Prerequisites 3 and 4 remain open.

Do not replace or promote the screenshots until all of the following are true:

1. `evidence/compatibility/live-gate.json` was produced by `nebius_token_factory`.
2. The report contains `real_provider=true` and `official_gate_passed=true`.
3. The public Judge Mode shows `LIVE / NEBIUS`, the exact NVIDIA model identifier, a redacted
   request ID, the trace ID and the physical mission result.
4. The physical AGV evidence has been reviewed by the safety owner.

## Required recapture

Replace all three files in one capture session:

- `01-completed.png`: completed physical mission, final pose and measured outcome.
- `02-model-tool-call.png`: real provider/model/request receipt and typed tool call.
- `03-verified-proof.png`: deterministic proof bound to the same trace and mission.

Every image must visibly show `LIVE / NEBIUS` and an `EVIDENCE UTC ...` timestamp. Update
`evidence/screenshots/manifest.json` to `evidence_class=final_competition`,
`final_submission_eligible=true`, `provider=nebius_token_factory`, `real_provider=true`, and add a
`live_provider_receipt` containing the exact `model`, `request_id` and `trace_id`. Recompute every
file hash; do not edit or reuse the fixture receipt.

## Fail-closed validation

Run:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli validate-final-evidence
```

The command exits non-zero while any screenshot is still a fixture, the live gate is absent, a
receipt field is missing, a hash differs, a timestamp is absent, or the visible scope label is not
`LIVE / NEBIUS`. Only an exit code of zero permits the final Evidence Bundle to be described as
submission-ready.
