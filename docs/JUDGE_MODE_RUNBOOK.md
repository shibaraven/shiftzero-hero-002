# Judge Mode runbook

This runbook is intentionally credential-free. It demonstrates the complete proof-carrying
mission loop using the deterministic reference simulator and labels that scope in the UI and
every evidence artifact.

## Fastest path

1. Open the published Judge Mode URL or start the local website from `apps/web` with
   `npm run dev`.
2. Select **Run Hero**. The replay advances through intent, observation, planning, proposal,
   deterministic verification, human approval, execution, blockage, local safe stop,
   replanning, re-verification, resumption, and completion.
3. Open **Architecture** to inspect the authority boundary: Nemotron may propose typed tools;
   deterministic policy and the state machine authorize execution.
4. Open **Evidence** to inspect the 100-scenario result, run manifest, fixture compatibility
   preflight, fair baseline, Judge load report, 400–500 pallets/day projection, typed tool spans,
   and downloadable Evidence Bundle.
5. Open **GitHub** to inspect repository readiness and the explicit public-release gate. The page
   never fabricates a source URL while no public remote exists.

Expected hero outcome: the simulated AGV stops after the N09 obstruction, takes the alternate
route only after re-verification, and completes at `N12` with final pose `x=6.0`, `y=0.0`,
`heading=315.0°` and an intact evidence hash chain.

## Reproduce from source

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m shiftzero.cli hero --provider fixture
.\.venv\Scripts\python.exe -m shiftzero.cli evaluate-scenarios
.\.venv\Scripts\python.exe -m shiftzero.cli verify-hero-reliability --runs 20
.\.venv\Scripts\python.exe -m shiftzero.cli fair-baseline --samples 20
.\.venv\Scripts\python.exe -m shiftzero.cli impact-load-model --sample-days 20
.\.venv\Scripts\python.exe -m shiftzero.cli build-hero-summary
.\.venv\Scripts\python.exe -m shiftzero.cli build-screenshot-manifest
.\.venv\Scripts\python.exe -m shiftzero.cli build-evidence-bundle
```

## Claims boundary

- `MOCK / FIXTURE` means locally reproducible simulator evidence and is visible in every capture.
- `LIVE GATE LOCKED` means no claim is made about live Token Factory execution.
- Physical AGV execution remains impossible until a real-provider Compatibility Gate passes
  and the site safety owner supplies the approved edge stop and transport interfaces.

The offline demo never reads secrets and never falls back from a failed live provider to a
fixture while retaining a live label.
