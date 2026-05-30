from datetime import datetime

from pydantic import BaseModel


class PipelineStageRunOut(BaseModel):
    id: str
    stage: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None


class PipelineRunOut(BaseModel):
    id: str
    project_id: str
    status: str
    current_stage: str | None
    idempotency_key: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    stage_runs: list[PipelineStageRunOut]
    log_summary: list[str]


class PipelineRunStartResponse(BaseModel):
    created: bool
    run: PipelineRunOut

