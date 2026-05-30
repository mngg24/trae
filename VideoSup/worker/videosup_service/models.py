from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class JobSceneIn(BaseModel):
    scene_id: str = Field(min_length=1)
    clip_url: str = Field(min_length=1)
    prompt: str = ""
    expected_duration_ms: int = Field(ge=0)


class SubtitleStyleIn(BaseModel):
    preset: str = Field(min_length=1)
    language: str | None = None
    max_chars_per_line: int | None = Field(default=None, ge=10)
    safe_area_pct: float | None = Field(default=None, ge=0, le=0.5)


class JobCreateRequest(BaseModel):
    schema_version: str = Field(default="1.0.0", min_length=1)
    project_id: str = Field(min_length=1)
    pipeline_run_id: str | None = None
    render_profile: Literal["preview", "final"] = "final"
    output_format: Literal["mp4", "hls"] = "mp4"
    scenes: list[JobSceneIn] = Field(min_length=1)
    voiceover_script: str = Field(min_length=1)
    subtitle_style: SubtitleStyleIn


class JobCreatedResponse(BaseModel):
    job_id: str


class ProgressOut(BaseModel):
    step: Literal["download", "normalize", "compose", "package", "upload"]
    pct: int = Field(ge=0, le=100)
    detail: str | None = None


class ErrorOut(BaseModel):
    code: str
    message: str
    strategy: Literal["retry", "abort"]


class JobStateOut(BaseModel):
    status: Literal["queued", "running", "succeeded", "failed", "canceled"]
    progress: ProgressOut | None = None
    error: ErrorOut | None = None


class OutputsOut(BaseModel):
    mp4_url: str | None = None
    hls_master_url: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    project_id: str
    created_at: datetime
    state: JobStateOut
    outputs: OutputsOut | None = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

