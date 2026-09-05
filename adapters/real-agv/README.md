# Real AGV adapter boundary

Real hardware integration is deliberately blocked until a real Nebius compatibility report has
`official_gate_passed=true`. The adapter must accept structured missions only; it must not expose
motor commands to the model. Local stop remains available when this service or the network fails.

