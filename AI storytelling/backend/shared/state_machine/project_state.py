from enum import StrEnum

from shared.state_machine.errors import InvalidStateTransition


class ProjectState(StrEnum):
    DRAFT = "DRAFT"
    SCRIPTING = "SCRIPTING"
    SCRIPT_READY = "SCRIPT_READY"
    ASSET_GENERATING = "ASSET_GENERATING"
    ASSETS_READY = "ASSETS_READY"
    RENDERING = "RENDERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


_ALLOWED_PROJECT_TRANSITIONS: dict[ProjectState, set[ProjectState]] = {
    ProjectState.DRAFT: {ProjectState.SCRIPTING},
    ProjectState.SCRIPTING: {ProjectState.SCRIPT_READY, ProjectState.FAILED},
    ProjectState.SCRIPT_READY: {ProjectState.ASSET_GENERATING},
    ProjectState.ASSET_GENERATING: {ProjectState.ASSETS_READY, ProjectState.FAILED},
    ProjectState.ASSETS_READY: {ProjectState.RENDERING},
    ProjectState.RENDERING: {ProjectState.COMPLETED, ProjectState.FAILED},
    ProjectState.COMPLETED: set(),
    ProjectState.FAILED: {ProjectState.SCRIPTING},
}


def is_allowed_project_transition(from_state: ProjectState, to_state: ProjectState) -> bool:
    return to_state in _ALLOWED_PROJECT_TRANSITIONS.get(from_state, set())


def assert_allowed_project_transition(from_state: ProjectState, to_state: ProjectState) -> None:
    if not is_allowed_project_transition(from_state, to_state):
        raise InvalidStateTransition(f"Invalid project transition: {from_state} -> {to_state}")

