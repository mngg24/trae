import unittest

from shared.state_machine import (
    InvalidStateTransition,
    PipelineRunStatus,
    ProjectState,
    assert_allowed_pipeline_run_transition,
    assert_allowed_project_transition,
    is_allowed_pipeline_run_transition,
    is_allowed_project_transition,
)


class TestStateMachine(unittest.TestCase):
    def test_project_transitions_matrix(self) -> None:
        states = list(ProjectState)
        for from_state in states:
            for to_state in states:
                with self.subTest(from_state=from_state, to_state=to_state):
                    if is_allowed_project_transition(from_state, to_state):
                        assert_allowed_project_transition(from_state, to_state)
                    else:
                        with self.assertRaises(InvalidStateTransition):
                            assert_allowed_project_transition(from_state, to_state)

    def test_run_transitions_matrix(self) -> None:
        states = list(PipelineRunStatus)
        for from_state in states:
            for to_state in states:
                with self.subTest(from_state=from_state, to_state=to_state):
                    if is_allowed_pipeline_run_transition(from_state, to_state):
                        assert_allowed_pipeline_run_transition(from_state, to_state)
                    else:
                        with self.assertRaises(InvalidStateTransition):
                            assert_allowed_pipeline_run_transition(from_state, to_state)


if __name__ == "__main__":
    unittest.main()
