import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.persistence.models import PipelineRun, PipelineStageRun


def generate_idempotency_key() -> str:
    return str(uuid.uuid4())


def get_or_create_pipeline_run(
    db: Session,
    *,
    project_id: str,
    idempotency_key: str | None,
) -> tuple[PipelineRun, bool]:
    if idempotency_key is None:
        pipeline_run = PipelineRun(project_id=project_id, idempotency_key=generate_idempotency_key())
        db.add(pipeline_run)
        db.commit()
        db.refresh(pipeline_run)
        return pipeline_run, True

    existing = db.execute(
        select(PipelineRun).where(
            PipelineRun.project_id == project_id,
            PipelineRun.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    pipeline_run = PipelineRun(project_id=project_id, idempotency_key=idempotency_key)
    db.add(pipeline_run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(PipelineRun).where(
                PipelineRun.project_id == project_id,
                PipelineRun.idempotency_key == idempotency_key,
            )
        ).scalar_one()
        return existing, False

    db.refresh(pipeline_run)
    return pipeline_run, True


def claim_pipeline_stage_run(
    db: Session,
    *,
    pipeline_run_id: str,
    stage: str,
) -> tuple[PipelineStageRun, bool]:
    existing = db.execute(
        select(PipelineStageRun).where(
            PipelineStageRun.pipeline_run_id == pipeline_run_id,
            PipelineStageRun.stage == stage,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    stage_run = PipelineStageRun(pipeline_run_id=pipeline_run_id, stage=stage)
    db.add(stage_run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(PipelineStageRun).where(
                PipelineStageRun.pipeline_run_id == pipeline_run_id,
                PipelineStageRun.stage == stage,
            )
        ).scalar_one()
        return existing, False

    db.refresh(stage_run)
    return stage_run, True

