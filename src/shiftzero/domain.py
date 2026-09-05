from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import to_jsonable_python


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_hash(value: Any) -> str:
    value = to_jsonable_python(value)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class MissionStatus(StrEnum):
    INTENT = "INTENT"
    NEEDS_INPUT = "NEEDS_INPUT"
    OBSERVED = "OBSERVED"
    PLANNED = "PLANNED"
    PROPOSED = "PROPOSED"
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    BLOCKED = "BLOCKED"
    SAFE_STOP = "SAFE_STOP"
    REPLANNING = "REPLANNING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    FAILED_SAFE = "FAILED_SAFE"


class ToolName(StrEnum):
    GET_OPERATIONAL_SNAPSHOT = "get_operational_snapshot"
    INSPECT_LOCATION = "inspect_location"
    PLAN_TRANSPORT = "plan_transport"
    PROPOSE_TRANSPORT = "propose_transport"
    APPROVE_TRANSPORT = "approve_transport"
    REJECT_TRANSPORT = "reject_transport"
    START_MISSION = "start_mission"
    STOP_MISSION = "stop_mission"
    GET_MISSION_STATUS = "get_mission_status"
    REPLAN_MISSION = "replan_mission"
    PROPOSE_RECOVERY = "propose_recovery"
    RESUME_MISSION = "resume_mission"
    OVERRIDE_MISSION = "override_mission"
    GET_OPERATION_METRICS = "get_operation_metrics"


class MissionIntent(StrictModel):
    pallet_id: str = Field(pattern=r"^[A-Z]+-\d+$")
    source: str = Field(pattern=r"^[A-Z]+(?:-[A-Z]+)*-\d+$")
    destination: str = Field(pattern=r"^[A-Z]+(?:-[A-Z]+)*-?[A-Z]*\d+$")
    requested_agv: str | None = Field(default=None, pattern=r"^AGV-\d+$")
    constraints: list[str] = Field(default_factory=lambda: ["avoid-human-zone"])

    @property
    def goal_hash(self) -> str:
        return canonical_hash(
            {
                "pallet_id": self.pallet_id,
                "source": self.source,
                "destination": self.destination,
                "constraints": sorted(self.constraints),
            }
        )


class MapNode(StrictModel):
    id: str
    x: float
    y: float
    zone: str
    capacity: int = 1
    allowed_vehicle_types: list[str] = Field(default_factory=lambda: ["AGV"])


class MapEdge(StrictModel):
    from_node: str
    to_node: str
    length_m: float = Field(gt=0)
    speed_limit_mps: float = Field(gt=0)
    reservation_group: str
    direction: Literal["bidirectional", "forward"] = "bidirectional"


class Pose(StrictModel):
    node_id: str
    x: float
    y: float
    heading_deg: float = Field(default=0, ge=0, lt=360)


class AgvState(StrictModel):
    id: str
    node_id: str
    state: Literal["IDLE", "CHARGING", "EXECUTING", "STOPPED", "OFFLINE"]
    battery_percent: float = Field(ge=0, le=100)
    capabilities: list[str]
    current_mission_id: str | None = None
    load_id: str | None = None
    pose: Pose | None = None


class LocationState(StrictModel):
    id: str
    node_id: str
    kind: Literal["INBOUND", "RACK", "STAGING"]
    occupancy: str | None = None
    pallet_id: str | None = None
    reachable: bool = True

    @model_validator(mode="after")
    def align_pallet_occupancy(self) -> LocationState:
        if self.occupancy is not None and self.pallet_id is None:
            self.pallet_id = self.occupancy
        elif self.pallet_id is not None and self.occupancy is None:
            self.occupancy = self.pallet_id
        elif self.pallet_id != self.occupancy:
            raise ValueError("pallet_id and occupancy must describe the same load")
        return self


class PalletState(StrictModel):
    id: str
    location_id: str


class ObstacleGeometry(StrictModel):
    type: Literal["Point", "Polygon"] = "Point"
    coordinates: list[float] | list[list[float]] = Field(default_factory=lambda: [0.0, 0.0])


class ObstacleState(StrictModel):
    id: str
    node_id: str
    confidence: float = Field(ge=0, le=1)
    source: str = "simulator"
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
    ttl_seconds: float = Field(default=30, gt=0)
    observation_count: int = Field(default=1, ge=1)
    geometry: ObstacleGeometry = Field(default_factory=ObstacleGeometry)


class RouteReservation(StrictModel):
    reservation_group: str
    held_by: str
    starts_at: datetime
    ends_at: datetime
    waiting_for: str | None = None

    @model_validator(mode="after")
    def validate_window(self) -> RouteReservation:
        if self.ends_at <= self.starts_at:
            raise ValueError("reservation ends_at must be after starts_at")
        return self


class OperationalSnapshot(StrictModel):
    snapshot_id: str
    captured_at: datetime
    map_version: str
    nodes: list[MapNode]
    edges: list[MapEdge]
    agvs: list[AgvState]
    locations: list[LocationState]
    pallets: list[PalletState]
    obstacles: list[ObstacleState] = Field(default_factory=list)
    reserved_groups: dict[str, str] = Field(default_factory=dict)
    route_reservations: list[RouteReservation] = Field(default_factory=list)
    wait_for: dict[str, str] = Field(default_factory=dict)


class LocationInspection(StrictModel):
    location_id: str
    exists: bool
    node_id: str | None = None
    occupancy: str | None = None
    snapshot_id: str


class RoutePlan(StrictModel):
    route_version: str
    map_version: str
    selected_agv: str
    nodes: list[str] = Field(min_length=2)
    reservation_groups: list[str]
    distance_m: float = Field(gt=0)
    estimated_energy_percent: float = Field(ge=0)
    cost: float = Field(ge=0)
    estimated_duration_seconds: float = Field(gt=0)
    candidate_count: int = Field(ge=1)


class RecoveryIntent(StrictModel):
    mission_id: str
    reason: str
    action: Literal["REPLAN", "WAIT", "ABORT"]
    blocked_node_id: str | None = None
    preserve_goal_hash: str
    requested_tools: list[ToolName] = Field(default_factory=lambda: [ToolName.REPLAN_MISSION])


class ToolEvidenceRef(StrictModel):
    ref: str
    tool_name: ToolName
    arguments_hash: str
    result_hash: str


class TransportProposal(StrictModel):
    proposal_id: str
    mission_goal: MissionIntent
    selected_agv: str
    route: list[str] = Field(min_length=2)
    route_version: str
    map_version: str
    snapshot_id: str
    evidence_refs: list[str] = Field(min_length=2)
    status: Literal[MissionStatus.PROPOSED] = MissionStatus.PROPOSED
    created_at: datetime = Field(default_factory=utc_now)
    proposal_hash: str

    @classmethod
    def issue(
        cls,
        *,
        proposal_id: str,
        intent: MissionIntent,
        plan: RoutePlan,
        snapshot_id: str,
        evidence_refs: list[str],
    ) -> TransportProposal:
        content = {
            "proposal_id": proposal_id,
            "mission_goal": intent.model_dump(mode="json"),
            "selected_agv": plan.selected_agv,
            "route": plan.nodes,
            "route_version": plan.route_version,
            "map_version": plan.map_version,
            "snapshot_id": snapshot_id,
            "evidence_refs": evidence_refs,
        }
        return cls(**content, proposal_hash=canonical_hash(content))


class SafetyCheck(StrictModel):
    name: str
    passed: bool
    detail: str
    evidence_hash: str


class SafetyProof(StrictModel):
    proof_id: str
    policy_version: str = "safety-v2"
    proposal_id: str
    route_version: str
    snapshot_id: str
    checks: list[SafetyCheck]
    passed: bool
    created_at: datetime = Field(default_factory=utc_now)
    proof_hash: str

    @classmethod
    def issue(
        cls,
        *,
        proposal_id: str,
        route_version: str,
        snapshot_id: str,
        checks: list[SafetyCheck],
    ) -> SafetyProof:
        content = {
            "proof_id": f"SP-{uuid.uuid4().hex[:10].upper()}",
            "policy_version": "safety-v2",
            "proposal_id": proposal_id,
            "route_version": route_version,
            "snapshot_id": snapshot_id,
            "checks": [check.model_dump(mode="json") for check in checks],
            "passed": all(check.passed for check in checks),
        }
        return cls(**content, proof_hash=canonical_hash(content))


class ApprovalToken(StrictModel):
    token_id: str
    proposal_hash: str
    goal_hash: str
    actor: str
    actor_role: Literal["approver", "admin"]
    issued_at: datetime
    expires_at: datetime
    approval_hash: str

    @classmethod
    def issue(
        cls,
        *,
        proposal_hash: str,
        goal_hash: str,
        actor: str,
        actor_role: Literal["approver", "admin"] = "approver",
        lifetime: timedelta = timedelta(minutes=15),
    ) -> ApprovalToken:
        issued_at = utc_now()
        content = {
            "token_id": f"APR-{uuid.uuid4().hex[:10].upper()}",
            "proposal_hash": proposal_hash,
            "goal_hash": goal_hash,
            "actor": actor,
            "actor_role": actor_role,
            "issued_at": issued_at,
            "expires_at": issued_at + lifetime,
        }
        return cls(
            **content,
            approval_hash=canonical_hash(content),
        )

    def valid_for(self, proposal: TransportProposal, *, at: datetime | None = None) -> bool:
        instant = at or utc_now()
        content = self.model_dump(mode="json", exclude={"approval_hash"})
        return (
            self.approval_hash == canonical_hash(content)
            and
            self.proposal_hash == proposal.proposal_hash
            and self.goal_hash == proposal.mission_goal.goal_hash
            and self.issued_at <= instant < self.expires_at
        )


class Mission(StrictModel):
    mission_id: str
    proposal_id: str
    proposal_hash: str
    goal_hash: str
    pallet_id: str
    source: str
    destination: str
    selected_agv: str
    route: list[str]
    route_version: str
    map_version: str
    snapshot_id: str
    proof_hash: str
    status: MissionStatus
    idempotency_key: str
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    current_node_index: int = 0


class ModelCallEvidence(StrictModel):
    provider: str
    model: str
    request_id: str
    started_at: datetime
    completed_at: datetime
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    tool_name: str
    tool_arguments_hash: str
    tool_result_hash: str
    retry_count: int = 0
    repair_count: int = 0
    http_status: int | None = None
    rate_limit_remaining: str | None = None
    rate_limit_reset: str | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    timed_out: bool = False
    fallback_state: str | None = None
    inference_budget_ms: float | None = Field(default=None, gt=0)


class HeroRunResult(StrictModel):
    trace_id: str
    provider: str
    model: str
    proposal_id: str
    mission_id: str
    initial_route_version: str
    replan_route_version: str
    final_status: MissionStatus
    stop_latency_ms: float
    stop_latency_kind: Literal["simulated_process", "physical_edge"]
    evidence_path: str
    state_history: list[MissionStatus]
    model_calls: list[ModelCallEvidence]
