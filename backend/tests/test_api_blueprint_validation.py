import os
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError as e:
    raise unittest.SkipTest(str(e))


def _valid_blueprint_payload(*, topic: str, target_duration_seconds: int) -> dict:
    return {
        "project_meta": {
            "topic": topic,
            "target_duration_seconds": target_duration_seconds,
            "estimated_scene_count": 1,
        },
        "scenes": [
            {
                "scene_number": 1,
                "narration_script": "n1",
                "image_generation_prompt": "p1",
                "camera_movement_suggestion": "c1",
                "estimated_duration_seconds": 30,
            }
        ],
    }


class TestBlueprintAPIValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls._tmpdir = tempfile.TemporaryDirectory()
            db_path = Path(cls._tmpdir.name) / "test_api.db"
            os.environ["DB_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"

            from api.main import app
            from shared.persistence.database import engine
            from shared.persistence.models import Base

            Base.metadata.create_all(engine)
            cls._engine = engine
            cls._Base = Base
            cls.client = TestClient(app)
        except ModuleNotFoundError as e:
            raise unittest.SkipTest(str(e))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def setUp(self) -> None:
        self._Base.metadata.drop_all(self._engine)
        self._Base.metadata.create_all(self._engine)

    def test_put_blueprint_topic_must_match_project_topic(self) -> None:
        resp = self.client.post(
            "/projects",
            json={"topic": "t1", "target_duration_seconds": 60},
        )
        self.assertEqual(resp.status_code, 201)
        project_id = resp.json()["id"]

        payload = _valid_blueprint_payload(topic="t2", target_duration_seconds=60)
        resp = self.client.put(f"/projects/{project_id}/blueprint", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("project_meta.topic", resp.json()["detail"])

    def test_put_blueprint_duration_must_match_project(self) -> None:
        resp = self.client.post(
            "/projects",
            json={"topic": "t1", "target_duration_seconds": 60},
        )
        self.assertEqual(resp.status_code, 201)
        project_id = resp.json()["id"]

        payload = _valid_blueprint_payload(topic="t1", target_duration_seconds=30)
        resp = self.client.put(f"/projects/{project_id}/blueprint", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("project_meta.target_duration_seconds", resp.json()["detail"])

    def test_put_get_blueprint_roundtrip(self) -> None:
        resp = self.client.post(
            "/projects",
            json={"topic": "t1", "target_duration_seconds": 60},
        )
        self.assertEqual(resp.status_code, 201)
        project_id = resp.json()["id"]

        payload = _valid_blueprint_payload(topic="t1", target_duration_seconds=60)
        resp = self.client.put(f"/projects/{project_id}/blueprint", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["project_meta"]["estimated_scene_count"], 1)

        resp = self.client.get(f"/projects/{project_id}/blueprint")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["project_meta"]["topic"], "t1")


if __name__ == "__main__":
    unittest.main()
