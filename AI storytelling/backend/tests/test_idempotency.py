import unittest

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except ModuleNotFoundError as e:
    raise unittest.SkipTest(str(e))

from shared.persistence.models import Base, Project
from shared.persistence.orchestration import claim_pipeline_stage_run, generate_idempotency_key, get_or_create_pipeline_run
from shared.state_machine import PipelineStage, ProjectState


class TestIdempotency(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def test_get_or_create_pipeline_run_idempotency_key(self) -> None:
        with self.SessionLocal() as db:
            project = Project(topic="t", target_duration_seconds=60, state=ProjectState.DRAFT)
            db.add(project)
            db.commit()
            db.refresh(project)

            run1, created1 = get_or_create_pipeline_run(
                db,
                project_id=project.id,
                idempotency_key="k1",
            )
            run2, created2 = get_or_create_pipeline_run(
                db,
                project_id=project.id,
                idempotency_key="k1",
            )

            self.assertTrue(created1)
            self.assertFalse(created2)
            self.assertEqual(run1.id, run2.id)

    def test_get_or_create_pipeline_run_without_key_creates_new_runs(self) -> None:
        with self.SessionLocal() as db:
            project = Project(topic="t", target_duration_seconds=60, state=ProjectState.DRAFT)
            db.add(project)
            db.commit()
            db.refresh(project)

            run1, created1 = get_or_create_pipeline_run(db, project_id=project.id, idempotency_key=None)
            run2, created2 = get_or_create_pipeline_run(db, project_id=project.id, idempotency_key=None)

            self.assertTrue(created1)
            self.assertTrue(created2)
            self.assertNotEqual(run1.id, run2.id)
            self.assertNotEqual(run1.idempotency_key, run2.idempotency_key)

    def test_claim_stage_run_idempotent(self) -> None:
        with self.SessionLocal() as db:
            project = Project(topic="t", target_duration_seconds=60, state=ProjectState.DRAFT)
            db.add(project)
            db.commit()
            db.refresh(project)

            run, _ = get_or_create_pipeline_run(db, project_id=project.id, idempotency_key="k2")

            stage1, acquired1 = claim_pipeline_stage_run(
                db,
                pipeline_run_id=run.id,
                stage=PipelineStage.GENERATE_BLUEPRINT,
            )
            stage2, acquired2 = claim_pipeline_stage_run(
                db,
                pipeline_run_id=run.id,
                stage=PipelineStage.GENERATE_BLUEPRINT,
            )

            self.assertTrue(acquired1)
            self.assertFalse(acquired2)
            self.assertEqual(stage1.id, stage2.id)

    def test_claim_stage_run_per_stage(self) -> None:
        with self.SessionLocal() as db:
            project = Project(topic="t", target_duration_seconds=60, state=ProjectState.DRAFT)
            db.add(project)
            db.commit()
            db.refresh(project)

            run, _ = get_or_create_pipeline_run(db, project_id=project.id, idempotency_key="k3")

            stage1, acquired1 = claim_pipeline_stage_run(
                db,
                pipeline_run_id=run.id,
                stage=PipelineStage.GENERATE_BLUEPRINT,
            )
            stage2, acquired2 = claim_pipeline_stage_run(
                db,
                pipeline_run_id=run.id,
                stage=PipelineStage.GENERATE_ASSETS,
            )

            self.assertTrue(acquired1)
            self.assertTrue(acquired2)
            self.assertNotEqual(stage1.id, stage2.id)

    def test_generate_idempotency_key_is_uuid(self) -> None:
        key1 = generate_idempotency_key()
        key2 = generate_idempotency_key()
        self.assertNotEqual(key1, key2)
        self.assertEqual(len(key1), 36)
        self.assertEqual(len(key2), 36)


if __name__ == "__main__":
    unittest.main()
