# Frozen architecture and trust boundaries

```text
Experience   CLI / signed Agent API / Judge Mode verified replay
Agent        Nemotron typed intent, proposal and RecoveryIntent only
Trust        schema -> live reference/version -> policy -> authenticated content-bound approval
Control      state gate -> SQLite idempotency receipt -> structured tool execution
Execution    SimulatorAdapter now; industrial adapter only after compatibility attestation
Physical     AGV/AGF, local safety controller, sensor and emergency stop
```

The controller owns tool order and side effects. The Agent layer receives only the tools allowed
for the current state. The Trust layer signs executable work; the Agent layer never does.

Mutating API calls authenticate a short-lived HMAC bearer token and derive actor and role from its
verified claims. Bodies cannot self-assert an approver or executor role. A SQLite WAL ledger keeps
exact-response idempotency receipts and an append-only decision audit. Missing auth configuration,
stale versions, reused keys with different inputs and interrupted operations all fail closed.

## Replan rule

A blockage always causes a local stop first. The Agent may then emit a typed, side-effect-free
`RecoveryIntent`. An equivalent route that preserves the approved
pallet, source, destination, constraints, and safety policy may be deterministically reverified
and exposed as `VERIFIED`; a separate executor-authorized Resume operation continues motion under
the existing mission authorization. A changed goal or controlled constraint
creates a new proposal and requires a new human approval.
