# Judge Mode runbook

This runbook is intentionally credential-free. It demonstrates the complete proof-carrying
mission loop using the deterministic reference simulator, and separately exposes the already
recorded live-provider Compatibility Gate without loading an API key in the browser.

## Fastest path

1. Open the published Judge Mode URL or start the local website from `apps/web` with
   `npm run dev`.
2. Select **Run Hero**. The replay advances through intent, observation, planning, proposal,
   deterministic verification, human approval, execution, blockage, local safe stop,
   replanning, re-verification, resumption, and completion.
3. Open **Architecture** to inspect the authority boundary: Nemotron may propose typed tools;
   deterministic policy and the state machine authorize execution.
4. Open **Evidence** to inspect the 100-scenario result, run manifest, fixture compatibility
   preflight, official live Compatibility Gate, fair baseline, Judge load report, 400–500
   pallets/day projection, typed tool spans, and downloadable Evidence Bundle. Select
   **Open field-test lab** to rehearse the nine-AGV A06/A07 blockage sequence in 2D or isometric
   view and export an explicitly ineligible simulator report.
5. Open **GitHub** to inspect the public source repository, required release files and the
   machine-readable public-repository receipt.

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
- `LIVE GATE PASSED` refers only to the archived Token Factory/Nemotron Compatibility Gate.
- `MOCK / FIXTURE` refers to the interactive replay and current screenshots.
- Physical AGV execution remains unavailable until the site safety owner supplies the approved
  OEM transport, mapped test area and edge-stop interfaces.
- The Field Test Lab prepares the onsite procedure but always reports `A06 NOT PASSED` and
  `A07 NOT PASSED`; see `docs/A06_A07_FIELD_TEST_PROTOCOL.md` for the physical closeout.

The offline demo never reads secrets and never falls back from a failed live provider to a
fixture while retaining a live label.

Public source: `https://github.com/shibaraven/shiftzero-hero-002`
