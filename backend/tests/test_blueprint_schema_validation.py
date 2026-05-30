import unittest

try:
    from pydantic import ValidationError
    from shared.schemas.blueprint import Blueprint
except ModuleNotFoundError as e:
    raise unittest.SkipTest(str(e))


def _valid_blueprint_dict() -> dict:
    return {
        "project_meta": {
            "topic": "topic",
            "target_duration_seconds": 60,
            "estimated_scene_count": 2,
        },
        "scenes": [
            {
                "scene_number": 1,
                "narration_script": "n1",
                "image_generation_prompt": "p1",
                "camera_movement_suggestion": "c1",
                "estimated_duration_seconds": 30,
            },
            {
                "scene_number": 2,
                "narration_script": "n2",
                "image_generation_prompt": "p2",
                "camera_movement_suggestion": "c2",
                "estimated_duration_seconds": 30,
            },
        ],
    }


class TestBlueprintSchemaValidation(unittest.TestCase):
    def test_valid_blueprint(self) -> None:
        bp = Blueprint.model_validate(_valid_blueprint_dict())
        self.assertEqual(bp.project_meta.estimated_scene_count, 2)
        self.assertEqual(len(bp.scenes), 2)

    def test_estimated_scene_count_must_match_len_scenes(self) -> None:
        payload = _valid_blueprint_dict()
        payload["project_meta"]["estimated_scene_count"] = 1
        with self.assertRaises(ValidationError):
            Blueprint.model_validate(payload)

    def test_scene_numbers_must_be_unique(self) -> None:
        payload = _valid_blueprint_dict()
        payload["scenes"][1]["scene_number"] = 1
        with self.assertRaises(ValidationError):
            Blueprint.model_validate(payload)

    def test_scene_numbers_must_be_contiguous_from_1(self) -> None:
        payload = _valid_blueprint_dict()
        payload["scenes"][1]["scene_number"] = 3
        with self.assertRaises(ValidationError):
            Blueprint.model_validate(payload)

    def test_scenes_must_not_be_empty(self) -> None:
        payload = _valid_blueprint_dict()
        payload["project_meta"]["estimated_scene_count"] = 0
        payload["scenes"] = []
        with self.assertRaises(ValidationError):
            Blueprint.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
