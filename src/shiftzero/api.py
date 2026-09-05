from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from shiftzero.agent import FixtureProvider, TokenFactoryProvider
from shiftzero.config import TokenFactorySettings
from shiftzero.domain import HeroRunResult, MissionStatus
from shiftzero.mission_service import MissionService, MissionServiceError
from shiftzero.simulator import load_default_scenario
from shiftzero.workflow import WorkflowController


class HeroRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["fixture", "nebius"] = "fixture"
    operator_text: str | None = None
    approval_actor: str


class IntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operator_text: str
    operator_id: str
    provider: Literal["fixture", "nebius"] = "fixture"


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_id: str


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str


class StopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str


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
    allow_headers=["Content-Type"],
)
service = MissionService(
    scenario=load_default_scenario(),
    evidence_root=Path("evidence/runs"),
)


def provider(name: Literal["fixture", "nebius"]):
    return (
        FixtureProvider()
        if name == "fixture"
        else TokenFactoryProvider(TokenFactorySettings.from_environment())
    )


def guarded(operation):
    try:
        return operation()
    except (MissionServiceError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{type(exc).__name__}: {exc}") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "safety_policy": "safety-v1"}


@app.get("/api/states")
def states() -> dict[str, list[str]]:
    return {"states": [state.value for state in MissionStatus]}


@app.post("/api/intents")
def create_intent(request: IntentRequest) -> dict[str, Any]:
    return guarded(
        lambda: service.view(
            service.create_intent(
                operator_text=request.operator_text,
                operator_id=request.operator_id,
                provider=provider(request.provider),
            )
        )
    )


@app.post("/api/proposals")
def create_proposal(request: ProposalRequest) -> dict[str, Any]:
    return guarded(lambda: service.view(service.prepare_proposal(request.intent_id)))


@app.get("/api/proposals/{proposal_id}/proof")
def get_proof(proposal_id: str) -> dict[str, Any]:
    return guarded(lambda: service.proof(proposal_id).model_dump(mode="json"))


@app.post("/api/proposals/{proposal_id}/approve")
def approve(proposal_id: str, request: ApprovalRequest) -> dict[str, Any]:
    return guarded(lambda: service.view(service.approve(proposal_id, actor=request.actor)))


@app.post("/api/missions/{mission_id}/start")
def start_mission(mission_id: str) -> dict[str, Any]:
    return guarded(lambda: service.view(service.start(mission_id)))


@app.post("/api/missions/{mission_id}/stop")
def stop_mission(mission_id: str, request: StopRequest) -> dict[str, Any]:
    return guarded(lambda: service.view(service.stop(mission_id, actor=request.actor)))


@app.post("/api/missions/{mission_id}/replan")
def replan_mission(mission_id: str) -> dict[str, Any]:
    return guarded(lambda: service.view(service.replan_and_complete(mission_id)))


@app.get("/api/missions/{mission_id}")
def mission_status(mission_id: str) -> dict[str, Any]:
    return guarded(lambda: service.status(mission_id))


@app.get("/api/traces/{trace_id}")
def trace(trace_id: str) -> list[dict[str, Any]]:
    return guarded(lambda: service.trace(trace_id))


@app.get("/api/metrics")
def metrics() -> dict[str, Any]:
    return service.metrics()


@app.post("/api/hero-runs", response_model=HeroRunResult)
def run_hero(request: HeroRunRequest) -> HeroRunResult:
    return guarded(
        lambda: WorkflowController(
            scenario=load_default_scenario(),
            provider=provider(request.provider),
            evidence_root=Path("evidence/runs"),
        ).run_hero(
            operator_text=request.operator_text,
            approval_actor=request.approval_actor,
        )
    )
