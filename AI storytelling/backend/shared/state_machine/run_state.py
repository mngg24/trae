from enum import StrEnum

from shared.state_machine.errors import InvalidStateTransition


class PipelineRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


_ALLOWED_PIPELINE_RUN_TRANSITIONS: dict[PipelineRunStatus, set[PipelineRunStatus]] = {
    PipelineRunStatus.PENDING: {PipelineRunStatus.RUNNING},
    PipelineRunStatus.RUNNING: {PipelineRunStatus.SUCCEEDED, PipelineRunStatus.FAILED},
    PipelineRunStatus.SUCCEEDED: set(),
    PipelineRunStatus.FAILED: set(),
}


def is_allowed_pipeline_run_transition(
    from_status: PipelineRunStatus,
    to_status: PipelineRunStatus,
) -> bool:
    return to_status in _ALLOWED_PIPELINE_RUN_TRANSITIONS.get(from_status, set())


def assert_allowed_pipeline_run_transition(
    from_status: PipelineRunStatus,
    to_status: PipelineRunStatus,
) -> None:
    if not is_allowed_pipeline_run_transition(from_status, to_status):
        raise InvalidStateTransition(f"Invalid pipeline run transition: {from_status} -> {to_status}")

