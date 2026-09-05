# Agent API service

The deployable FastAPI application is `shiftzero.api:app`. Run it from the installed project:

```powershell
$env:SHIFTZERO_AUTH_SECRET = "generate-at-least-32-random-characters"
uvicorn shiftzero.api:app --host 127.0.0.1 --port 8000
```

The HTTP layer never bypasses the same controller, trust checks, and adapter gates used by CLI
and tests. Every write requires a signed short-lived bearer identity, idempotency key and expected
version. Exact responses and decision hashes are persisted in the SQLite WAL ledger configured by
`SHIFTZERO_LEDGER_PATH`. See `docs/AUTHORIZATION.md` for roles and token issuance.
