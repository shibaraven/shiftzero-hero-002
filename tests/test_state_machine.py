import pytest

from shiftzero.domain import MissionStatus
from shiftzero.state_machine import InvalidTransition, WorkflowState


def test_happy_path_state_transitions_are_explicit() -> None:
    state = WorkflowState()
    for target in (
        MissionStatus.OBSERVED,
        MissionStatus.PLANNED,
        MissionStatus.PROPOSED,
        MissionStatus.VERIFIED,
        MissionStatus.APPROVED,
        MissionStatus.EXECUTING,
        MissionStatus.BLOCKED,
        MissionStatus.SAFE_STOP,
        MissionStatus.REPLANNING,
        MissionStatus.VERIFIED,
        MissionStatus.EXECUTING,
        MissionStatus.COMPLETED,
    ):
        state.transition(target)
    assert state.current == MissionStatus.COMPLETED


def test_model_cannot_skip_from_proposed_to_execution() -> None:
    state = WorkflowState(current=MissionStatus.PROPOSED, history=[MissionStatus.PROPOSED])
    with pytest.raises(InvalidTransition):
        state.transition(MissionStatus.EXECUTING)


def test_terminal_state_cannot_resume() -> None:
    state = WorkflowState(current=MissionStatus.FAILED_SAFE, history=[MissionStatus.FAILED_SAFE])
    with pytest.raises(InvalidTransition):
        state.transition(MissionStatus.EXECUTING)
