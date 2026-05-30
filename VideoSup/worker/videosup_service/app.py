from __future__ import annotations

import os
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException

from videosup_worker.contracts import MediaJobValidationError, validate_media_job_spec
from videosup_worker.fetcher.fetcher import Fetcher, FetcherConfig
from videosup_worker.pipeline import Pipeline, PipelineConfig

from .models import (
    ErrorOut,
    JobCreateRequest,
    JobCreatedResponse,
    JobStateOut,
    JobStatusResponse,
    OutputsOut,
    ProgressOut,
    utcnow,
)
from .state import JobEntry, JobStore


app = FastAPI(title="VideoSup Service")
store = JobStore()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/jobs", response_model=JobCreatedResponse, status_code=201)
def create_job(payload: JobCreateRequest) -> JobCreatedResponse:
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    entry = JobEntry(
        job_id=job_id,
        project_id=payload.project_id,
        created_at=utcnow(),
        state=JobStateOut(status="queued"),
        outputs=None,
    )
    store.create(entry)

    t = threading.Thread(target=_run_job, kwargs={"job_id": job_id, "payload": payload}, daemon=True)
    t.start()

    return JobCreatedResponse(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    e = store.get(job_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=e.job_id,
        project_id=e.project_id,
        created_at=e.created_at,
        state=e.state,
        outputs=e.outputs,
    )


def _run_job(*, job_id: str, payload: JobCreateRequest) -> None:
    try:
        store.update_state(
            job_id,
            JobStateOut(status="running", progress=ProgressOut(step="download", pct=5, detail="Downloading clips")),
        )
        work_root = Path(os.getenv("VIDEOSUP_SERVICE_WORK_DIR", ".work/videosup-service")).resolve()
        job_dir = (work_root / job_id).resolve()
        job_dir.mkdir(parents=True, exist_ok=True)

        fetcher = Fetcher(config=_fetcher_config_from_env())
        fetched = fetcher.fetch_many(job_id=job_id, urls=[s.clip_url for s in payload.scenes], step="download")
        clip_paths = [r.path for r in fetched]

        store.update_state(
            job_id,
            JobStateOut(status="running", progress=ProgressOut(step="normalize", pct=25, detail="Preparing pipeline")),
        )

        created_at = payload.model_dump().get("created_at") or utcnow().isoformat()
        spec_dict = {
            "schema_version": payload.schema_version,
            "job_id": job_id,
            "project_id": payload.project_id,
            "created_at": created_at,
            "render_profile": payload.render_profile,
            "output_format": payload.output_format,
            "scenes": [s.model_dump() for s in payload.scenes],
            "voiceover_script": payload.voiceover_script,
            "subtitle_style": payload.subtitle_style.model_dump(),
            "state": {"status": "queued"},
        }
        spec = validate_media_job_spec(spec_dict)

        voice_path = job_dir / "voice.wav"
        duration_sec = _expected_duration_sec(payload)
        _generate_placeholder_voice(voice_path=voice_path, duration_sec=duration_sec)

        cfg = PipelineConfig(
            work_dir=job_dir / "work",
            cache_dir=job_dir / "cache",
        )
        pipeline = Pipeline(config=cfg)

        store.update_state(
            job_id,
            JobStateOut(status="running", progress=ProgressOut(step="compose", pct=45, detail="Rendering video")),
        )
        res = pipeline.run(job_id=job_id, spec=spec, clip_paths=clip_paths, voiceover_audio_path=voice_path)

        store.update_state(
            job_id,
            JobStateOut(status="running", progress=ProgressOut(step="upload", pct=85, detail="Uploading outputs")),
        )

        outputs = OutputsOut(mp4_url=res.mp4_url, hls_master_url=res.hls_master_url)
        store.update_outputs(job_id, outputs)
        store.update_state(job_id, JobStateOut(status="succeeded"))
    except MediaJobValidationError as exc:
        store.update_state(
            job_id,
            JobStateOut(
                status="failed",
                error=ErrorOut(code="VALIDATION_ERROR", message=str(exc), strategy="abort"),
            ),
        )
    except Exception as exc:
        store.update_state(
            job_id,
            JobStateOut(
                status="failed",
                error=ErrorOut(code="FAILED", message=_safe_err(str(exc)), strategy="abort"),
            ),
        )


def _expected_duration_sec(payload: JobCreateRequest) -> float:
    total_ms = sum(s.expected_duration_ms for s in payload.scenes)
    if total_ms <= 0:
        return 2.5
    return max(1.0, total_ms / 1000.0)


def _fetcher_config_from_env() -> FetcherConfig:
    return FetcherConfig(
        timeout_sec=float(os.getenv("VIDEOSUP_FETCH_TIMEOUT_SEC", "60")),
        max_concurrency=int(os.getenv("VIDEOSUP_FETCH_MAX_CONCURRENCY", "4")),
        max_retries=int(os.getenv("VIDEOSUP_FETCH_MAX_RETRIES", "3")),
        cache_dir=Path(os.getenv("VIDEOSUP_FETCH_CACHE_DIR", ".cache/videosup/fetcher")).resolve(),
    )


def _generate_placeholder_voice(*, voice_path: Path, duration_sec: float) -> None:
    voice_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_sec}",
        "-c:a",
        "pcm_s16le",
        "-ar",
        "48000",
        "-ac",
        "1",
        str(voice_path),
    ]
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "ffmpeg_failed")[-4000:])


def _safe_err(msg: str) -> str:
    m = (msg or "error").strip()
    if len(m) > 600:
        return m[:600]
    return m

