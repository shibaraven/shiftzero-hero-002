# Agent API service

The deployable FastAPI application is `shiftzero.api:app`. Run it from the installed project:

```powershell
uvicorn shiftzero.api:app --host 127.0.0.1 --port 8000
```

The HTTP layer never bypasses the same controller, trust checks, and adapter gates used by CLI
and tests.

