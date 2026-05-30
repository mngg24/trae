import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _posix_sqlite_db_url(db_path: Path) -> str:
    return f"sqlite+pysqlite:///{db_path.resolve().as_posix()}"


class TestE2EMockRun(unittest.TestCase):
    def test_pipeline_completes_with_mock_providers(self) -> None:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import sessionmaker

        from shared.persistence.models import Asset, Base, PipelineRun, PipelineStageRun, Project, Scene
        from shared.state_machine import PipelineRunStatus, PipelineStage, ProjectState
        from worker.celery_app import celery_app
        from worker import tasks as worker_tasks

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_e2e.db"
            os.environ["DB_URL"] = _posix_sqlite_db_url(db_path)
            os.environ["PROVIDERS_MODE"] = "mock"

            engine = create_engine(
                os.environ["DB_URL"],
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
            try:
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                Base.metadata.create_all(engine)

                with SessionLocal() as db:
                    project = Project(topic="e2e topic", target_duration_seconds=60, state=ProjectState.DRAFT)
                    db.add(project)
                    db.commit()
                    db.refresh(project)
                    project_id = project.id

                    run = PipelineRun(project_id=project.id, idempotency_key="test-e2e")
                    db.add(run)
                    db.commit()
                    db.refresh(run)
                    run_id = run.id

                def _local_send_task(name: str, args=None, kwargs=None, **_extra):
                    task = celery_app.tasks[name]
                    return task.apply(args=args or (), kwargs=kwargs or {}).get()

                with patch.object(worker_tasks, "SessionLocal", new=SessionLocal):
                    with patch.object(celery_app, "send_task", new=_local_send_task):
                        worker_tasks.kickoff_pipeline_run.apply(
                            kwargs={"project_id": project_id, "pipeline_run_id": run_id}
                        ).get()

                with SessionLocal() as db:
                    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
                    run = db.execute(select(PipelineRun).where(PipelineRun.id == run_id)).scalar_one()

                    scenes = db.execute(select(Scene).where(Scene.project_id == project.id)).scalars().all()
                    assets = db.execute(select(Asset).where(Asset.project_id == project.id)).scalars().all()
                    stage_rows = (
                        db.execute(select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == run_id))
                        .scalars()
                        .all()
                    )

                self.assertEqual(project.state, ProjectState.COMPLETED)
                self.assertEqual(run.status, PipelineRunStatus.SUCCEEDED)
                self.assertIsNone(run.current_stage)
                self.assertTrue(scenes)
                self.assertGreater(len(assets), 0)

                asset_types = {a.asset_type for a in assets}
                self.assertTrue({"image", "audio", "video"}.issubset(asset_types))

                scene_states = {s.status for s in scenes}
                self.assertEqual(scene_states, {"READY"})

                stage_names = {
                    PipelineStage.GENERATE_BLUEPRINT,
                    PipelineStage.GENERATE_ASSETS,
                    PipelineStage.RENDER_ASSEMBLE,
                }
                stage_runs = {sr.stage: sr.status for sr in stage_rows}
                self.assertTrue(stage_names.issubset(set(stage_runs.keys())))
                self.assertEqual(set(stage_runs.values()), {"SUCCEEDED"})
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
