# Security policy

## Supported version

Only the latest commit on the default branch is supported during the competition.

## Reporting

Do not open a public issue for secrets, actuator-control bypasses, unsafe resume behavior, or
other vulnerabilities that could cause physical movement. Contact the repository owner through
the private channel listed in the competition submission.

## Non-negotiable controls

- Secrets are server-side environment variables and never enter source, traces, screenshots,
  browser bundles, or evidence archives.
- Model output is untrusted input and cannot directly reach an execution adapter.
- A valid, unexpired approval bound to the proposal hash is required for initial dispatch.
- Sensor-triggered stop is local and independent of the model, cloud, and public network.
- Reconnection never resumes a mission automatically.

