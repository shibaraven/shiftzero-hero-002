# Nebius Serverless Jobs handoff

The scenario evaluator is packaged as a non-interactive CLI job. A job runner invokes:

```text
shiftzero evaluate-scenarios --manifest scenarios/evaluation_manifest.json --output /output
```

Expected outputs are `scenario-results.jsonl`, `metrics.json`, `run-manifest.json`, and an optional
`failed_cases/` directory. The process exits non-zero on invalid input or an unhandled control-plane
failure. The run manifest binds the result to source revision, source-tree hash, map hash, seed,
provider/model identity, prompt/tool-schema versions, and safety-policy version.

The command is cloud-neutral and ready for a container or Serverless Jobs wrapper. Deployment to a
Nebius project is intentionally gated on account credentials, project/region selection, artifact
registry access, and an approved storage destination. No cloud deployment is claimed by this repo.
