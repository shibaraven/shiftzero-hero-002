# Frozen architecture and trust boundaries

```text
Experience   CLI / Agent API / future Judge Mode
Agent        Nemotron on Token Factory, typed calls only
Trust        workflow state gate -> schema -> reference/version -> policy -> approval
Execution    SimulatorAdapter now; industrial adapter only after compatibility attestation
Physical     AGV/AGF, local safety controller, sensor and emergency stop
```

The controller owns tool order and side effects. The Agent layer receives only the tools allowed
for the current state. The Trust layer signs executable work; the Agent layer never does.

## Replan rule

A blockage always causes a local stop first. An equivalent route that preserves the approved
pallet, source, destination, constraints, and safety policy may be deterministically reverified
and resumed under the existing mission authorization. A changed goal or controlled constraint
creates a new proposal and requires a new human approval.

