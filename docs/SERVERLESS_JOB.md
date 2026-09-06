# Nebius Serverless Jobs handoff

`Dockerfile.serverless` packages the deterministic 100-scenario evaluator as a non-interactive
job. Its immutable application entrypoint is:

```text
shiftzero evaluate-scenarios --manifest scenarios/evaluation_manifest.json --output /output
```

Expected outputs are `scenario-results.jsonl`, `metrics.json`, `run-manifest.json`, and an optional
`failed_cases/` directory. The process exits non-zero on invalid input or an unhandled control-plane
failure. The run manifest binds results to source revision, source-tree hash, map hash, seed,
provider/model identity, prompt/tool-schema versions, and safety-policy version. The evaluator uses
the deterministic fixture provider, so the job needs no Token Factory key and makes no live-model or
physical-hardware claim.

## Reproduce the job locally

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli evaluate-scenarios `
  --manifest scenarios/evaluation_manifest.json `
  --output tmp/serverless-smoke
.\.venv\Scripts\python.exe -m shiftzero.cli serverless-readiness `
  --smoke-output tmp/serverless-smoke
```

The checked-in `evidence/serverless-readiness.json` is fail-closed. `artifact_ready=true` means the
same CLI entrypoint produced all 100 expected outcomes with zero observed safety violations.
`cloud_deployed=true` is impossible unless a separately captured
`evidence/serverless-deployment-receipt.json` proves a successful Nebius job ID and output hash.

## Cloud release procedure

1. An administrator creates or selects a Nebius AI Cloud project with Serverless/VM quota.
2. Configure the Nebius CLI with that project and export `NEBIUS_PROJECT_ID`.
3. Build `Dockerfile.serverless`, push the immutable digest to an accessible container registry,
   and export `NEBIUS_SERVERLESS_IMAGE_URI`.
4. Create a Nebius Serverless AI job using that digest and the image's default entrypoint.
5. Persist `/output`, wait for `SUCCEEDED`, download the three expected artifacts, verify their
   hashes, and capture the job ID, image digest, region, timestamps, exit code, and output manifest
   in `evidence/serverless-deployment-receipt.json`.
6. Rerun `serverless-readiness`; only a valid receipt may change `cloud_deployed` to true.

Token Factory inference credentials are not Nebius AI Cloud project credentials. This repository
does not silently use one as the other and does not claim a cloud deployment from a local smoke
test.
