from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from shiftzero.agent import FixtureProvider, TokenFactoryProvider
from shiftzero.auth import (
    AuthenticationError,
    AuthSettings,
    Principal,
    Role,
    verify_access_token,
)
from shiftzero.config import TokenFactorySettings
from shiftzero.domain import HeroRunResult, MissionStatus, canonical_hash
from shiftzero.mission_service import (
    MissionConflictError,
    MissionPermissionError,
    MissionService,
    MissionServiceError,
)
from shiftzero.simulator import load_default_scenario
from shiftzero.storage import LedgerConflictError, SqliteOperationLedger
from shiftzero.workflow import WorkflowController


class NewResourceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)
    expected_version: Literal[0]


class ExistingResourceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=128)
    expected_version: int = Field(ge=1)


class HeroRunRequest(NewResourceWrite):
    provider: Literal["fixture", "nebius"] = "fixture"
    operator_text: str | None = None


class IntentRequest(NewResourceWrite):
    operator_text: str
    provider: Literal["fixture", "nebius"] = "fixture"


class ProposalRequest(ExistingResourceWrite):
    intent_id: str


class ApprovalRequest(ExistingResourceWrite):
    pass


class RejectRequest(ApprovalRequest):
    reason: str = Field(min_length=3, max_length=500)


class StartRequest(ExistingResourceWrite):
    pass


class StopRequest(ExistingResourceWrite):
    trigger_source: str = Field(default="operator-panel", min_length=3, max_length=128)


class ReplanRequest(ExistingResourceWrite):
    blocked_node_id: str | None = None


class OverrideRequest(ExistingResourceWrite):
    reason: str = Field(min_length=8, max_length=500)


app = FastAPI(
    title="ShiftZero HERO-002 Agent API",
    version="0.2.0",
    description="Typed, state-gated proof-carrying warehouse mission reference API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
)
service = MissionService(
    scenario=load_default_scenario(),
    evidence_root=Path("evidence/runs"),
)
security = HTTPBearer(auto_error=False)
_ledgers: dict[Path, SqliteOperationLedger] = {}
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(security)]


def provider(name: Literal["fixture", "nebius"]):
    return (
        FixtureProvider()
        if name == "fixture"
        else TokenFactoryProvider(TokenFactorySettings.from_environment())
    )


def guarded(operation):
    try:
        return operation()
    except MissionConflictError as exc:
        raise HTTPException(status_code=409, detail=f"{type(exc).__name__}: {exc}") from exc
    except MissionPermissionError as exc:
        raise HTTPException(status_code=403, detail=f"{type(exc).__name__}: {exc}") from exc
    except LedgerConflictError as exc:
        raise HTTPException(status_code=409, detail=f"{type(exc).__name__}: {exc}") from exc
    except (MissionServiceError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{type(exc).__name__}: {exc}") from exc


def authenticated_principal(
    credentials: BearerCredentials,
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="a signed bearer token is required")
    try:
        settings = AuthSettings.from_environment()
    except AuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        return verify_access_token(credentials.credentials, settings)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


AuthenticatedPrincipal = Annotated[Principal, Depends(authenticated_principal)]


def require_role(principal: Principal, allowed: set[Role]) -> None:
    if principal.role not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"authenticated role {principal.role!r} requires one of {sorted(allowed)}",
        )


def operation_ledger() -> SqliteOperationLedger:
    path = Path(os.getenv("SHIFTZERO_LEDGER_PATH", "output/agent-api.sqlite3")).resolve()
    if path not in _ledgers:
        _ledgers[path] = SqliteOperationLedger(path)
    return _ledgers[path]


def durable_mutation(
    *,
    operation: str,
    request: NewResourceWrite | ExistingResourceWrite,
    principal: Principal,
    payload: dict[str, Any],
    resource_id: str,
    decision: str,
    callback: Any,
) -> dict[str, Any]:
    authenticated_payload = {
        **payload,
        "actor": principal.subject,
        "role": principal.role,
        "expected_version": request.expected_version,
    }
    response, replayed = operation_ledger().execute(
        operation=operation,
        idempotency_key=request.idempotency_key,
        fingerprint=canonical_hash(authenticated_payload),
        callback=callback,
    )
    if not replayed:
        operation_ledger().append_audit(
            operation=operation,
            actor=principal.subject,
            role=principal.role,
            resource_id=resource_id,
            decision=decision,
            payload=authenticated_payload,
        )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "safety_policy": "safety-v2"}


@app.get("/api/states")
def states() -> dict[str, list[str]]:
    return {"states": [state.value for state in MissionStatus]}


@app.post("/api/intents")
def create_intent(
    request: IntentRequest, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    require_role(principal, {"operator", "approver", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation="intent:create",
            request=request,
            principal=principal,
            payload={"operator_text": request.operator_text, "provider": request.provider},
            resource_id="new-intent",
            decision="CREATE",
            callback=lambda: service.view(
                service.create_intent(
                    operator_text=request.operator_text,
                    operator_id=principal.subject,
                    provider=provider(request.provider),
                )
            ),
        )
    )


@app.post("/api/proposals")
def create_proposal(
    request: ProposalRequest, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    require_role(principal, {"operator", "approver", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"intent:{request.intent_id}:prepare",
            request=request,
            principal=principal,
            payload={"intent_id": request.intent_id},
            resource_id=request.intent_id,
            decision="PREPARE",
            callback=lambda: service.view(
                service.prepare_proposal(
                    request.intent_id,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.get("/api/proposals/{proposal_id}/proof")
def get_proof(proposal_id: str) -> dict[str, Any]:
    return guarded(lambda: service.proof(proposal_id).model_dump(mode="json"))


@app.post("/api/proposals/{proposal_id}/approve")
def approve(
    proposal_id: str,
    request: ApprovalRequest,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    require_role(principal, {"approver", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"proposal:{proposal_id}:approve",
            request=request,
            principal=principal,
            payload={"proposal_id": proposal_id},
            resource_id=proposal_id,
            decision="APPROVE",
            callback=lambda: service.view(
                service.approve(
                    proposal_id,
                    actor=principal.subject,
                    actor_role=principal.role,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.post("/api/proposals/{proposal_id}/reject")
def reject(
    proposal_id: str,
    request: RejectRequest,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    require_role(principal, {"approver", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"proposal:{proposal_id}:reject",
            request=request,
            principal=principal,
            payload={"proposal_id": proposal_id, "reason": request.reason},
            resource_id=proposal_id,
            decision="REJECT",
            callback=lambda: service.view(
                service.reject(
                    proposal_id,
                    actor=principal.subject,
                    actor_role=principal.role,
                    reason=request.reason,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.post("/api/missions/{mission_id}/start")
def start_mission(
    mission_id: str,
    request: StartRequest,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    require_role(principal, {"executor", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"mission:{mission_id}:start",
            request=request,
            principal=principal,
            payload={"mission_id": mission_id},
            resource_id=mission_id,
            decision="START",
            callback=lambda: service.view(
                service.start(
                    mission_id,
                    actor=principal.subject,
                    actor_role=principal.role,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.post("/api/missions/{mission_id}/stop")
def stop_mission(
    mission_id: str,
    request: StopRequest,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    require_role(principal, {"safety", "executor", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"mission:{mission_id}:stop",
            request=request,
            principal=principal,
            payload={"mission_id": mission_id, "trigger_source": request.trigger_source},
            resource_id=mission_id,
            decision="STOP",
            callback=lambda: service.view(
                service.stop(
                    mission_id,
                    actor=principal.subject,
                    actor_role=principal.role,
                    trigger_source=request.trigger_source,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.post("/api/missions/{mission_id}/replan")
def replan_mission(
    mission_id: str,
    request: ReplanRequest,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    require_role(principal, {"operator", "executor", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"mission:{mission_id}:replan",
            request=request,
            principal=principal,
            payload={"mission_id": mission_id, "blocked_node_id": request.blocked_node_id},
            resource_id=mission_id,
            decision="REPLAN",
            callback=lambda: service.view(
                service.replan(
                    mission_id,
                    actor=principal.subject,
                    actor_role=principal.role,
                    blocked_node_id=request.blocked_node_id,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.post("/api/missions/{mission_id}/resume")
def resume_mission(
    mission_id: str,
    request: ExistingResourceWrite,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    require_role(principal, {"executor", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"mission:{mission_id}:resume",
            request=request,
            principal=principal,
            payload={"mission_id": mission_id},
            resource_id=mission_id,
            decision="RESUME",
            callback=lambda: service.view(
                service.resume_and_complete(
                    mission_id,
                    actor=principal.subject,
                    actor_role=principal.role,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.post("/api/missions/{mission_id}/override")
def override_mission(
    mission_id: str,
    request: OverrideRequest,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    require_role(principal, {"safety", "admin"})
    return guarded(
        lambda: durable_mutation(
            operation=f"mission:{mission_id}:override",
            request=request,
            principal=principal,
            payload={"mission_id": mission_id, "reason": request.reason},
            resource_id=mission_id,
            decision="OVERRIDE_TO_FAILED_SAFE",
            callback=lambda: service.view(
                service.override_to_failed_safe(
                    mission_id,
                    actor=principal.subject,
                    actor_role=principal.role,
                    reason=request.reason,
                    idempotency_key=request.idempotency_key,
                    expected_version=request.expected_version,
                )
            ),
        )
    )


@app.get("/api/missions/{mission_id}")
def mission_status(mission_id: str) -> dict[str, Any]:
    return guarded(lambda: service.status(mission_id))


@app.get("/api/traces/{trace_id}")
def trace(trace_id: str) -> list[dict[str, Any]]:
    return guarded(lambda: service.trace(trace_id))


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    return service.metrics()


@app.get("/api/audit")
def audit(
    principal: AuthenticatedPrincipal, limit: int = 100
) -> list[dict[str, Any]]:
    require_role(principal, {"viewer", "safety", "admin"})
    return operation_ledger().list_audit(limit=limit)


@app.post("/api/hero-runs", response_model=HeroRunResult)
def run_hero(
    request: HeroRunRequest, principal: AuthenticatedPrincipal
) -> HeroRunResult:
    require_role(principal, {"approver", "admin"})
    return guarded(
        lambda: HeroRunResult.model_validate(
            durable_mutation(
                operation="hero:run",
                request=request,
                principal=principal,
                payload={"provider": request.provider, "operator_text": request.operator_text},
                resource_id="hero-run",
                decision="RUN_HERO",
                callback=lambda: WorkflowController(
                    scenario=load_default_scenario(),
                    provider=provider(request.provider),
                    evidence_root=Path("evidence/runs"),
                )
                .run_hero(
                    operator_text=request.operator_text,
                    approval_actor=principal.subject,
                )
                .model_dump(mode="json"),
            )
        )
    )
