# Agent API authentication and authorization

All mutating endpoints require a short-lived HMAC-SHA256 bearer token. The verified token supplies
the actor identifier and role; request bodies cannot self-assert either value. Set a random
`SHIFTZERO_AUTH_SECRET` of at least 32 characters outside Git, then issue a token with:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli issue-auth-token `
  --subject operator@example.invalid --role operator --ttl-seconds 900
```

Supported least-privilege roles are `operator`, `approver`, `executor`, `safety`, `viewer`, and
`admin`. Approval and rejection require `approver`; start and resume require `executor`; stop and
fail-safe override require `safety` or an executor where explicitly allowed. Override never
authorizes motion: it invalidates approval and terminates the workflow as `FAILED_SAFE`.

Every write body contains `idempotency_key` and `expected_version`. New-resource writes use
version `0`; existing-resource writes use the current positive version. A SQLite WAL ledger stores
the authenticated request fingerprint and exact committed response. Reusing a key with different
input returns HTTP 409. The separate append-only `decision_audit` table records actor, verified
role, resource, decision, timestamp, and payload hash without storing bearer tokens.

Missing or weak authentication configuration fails closed. The public Judge replay performs no
mutating API calls and therefore never embeds credentials in browser assets.
