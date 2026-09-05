from __future__ import annotations

from dataclasses import dataclass, field

from shiftzero.domain import MissionStatus


class InvalidTransition(RuntimeError):
    pass


ALLOWED_TRANSITIONS: dict[MissionStatus, frozenset[MissionStatus]] = {
    MissionStatus.INTENT: frozenset({MissionStatus.OBSERVED, MissionStatus.NEEDS_INPUT}),
    MissionStatus.NEEDS_INPUT: frozenset({MissionStatus.INTENT, MissionStatus.REJECTED}),
    MissionStatus.OBSERVED: frozenset({MissionStatus.PLANNED, MissionStatus.FAILED_SAFE}),
    MissionStatus.PLANNED: frozenset({MissionStatus.PROPOSED, MissionStatus.REJECTED}),
    MissionStatus.PROPOSED: frozenset({MissionStatus.VERIFIED, MissionStatus.REJECTED}),
    MissionStatus.VERIFIED: frozenset(
        {MissionStatus.APPROVED, MissionStatus.EXECUTING, MissionStatus.REJECTED}
    ),
    MissionStatus.APPROVED: frozenset(
        {MissionStatus.EXECUTING, MissionStatus.REJECTED, MissionStatus.FAILED_SAFE}
    ),
    MissionStatus.EXECUTING: frozenset(
        {MissionStatus.BLOCKED, MissionStatus.COMPLETED, MissionStatus.FAILED_SAFE}
    ),
    MissionStatus.BLOCKED: frozenset({MissionStatus.SAFE_STOP, MissionStatus.FAILED_SAFE}),
    MissionStatus.SAFE_STOP: frozenset({MissionStatus.REPLANNING, MissionStatus.FAILED_SAFE}),
    MissionStatus.REPLANNING: frozenset({MissionStatus.VERIFIED, MissionStatus.FAILED_SAFE}),
    MissionStatus.COMPLETED: frozenset(),
    MissionStatus.REJECTED: frozenset(),
    MissionStatus.FAILED: frozenset(),
    MissionStatus.FAILED_SAFE: frozenset(),
}


@dataclass(slots=True)
class WorkflowState:
    current: MissionStatus = MissionStatus.INTENT
    history: list[MissionStatus] = field(default_factory=lambda: [MissionStatus.INTENT])

    def transition(self, target: MissionStatus) -> None:
        if target not in ALLOWED_TRANSITIONS[self.current]:
            raise InvalidTransition(f"transition {self.current} -> {target} is forbidden")
        self.current = target
        self.history.append(target)
