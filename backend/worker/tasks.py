from datetime import datetime, timezone
import os
import time
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select, update

from shared.config import get_settings
from shared.persistence import SessionLocal, claim_pipeline_stage_run
from shared.persistence.models import Asset, PipelineRun, PipelineStageRun, Project, Scene
from shared.providers.factory import get_providers
from shared.schemas.blueprint import Blueprint
from shared.state_machine import (
    PipelineRunStatus,
    PipelineStage,
    ProjectState,
    assert_allowed_pipeline_run_transition,
    assert_allowed_project_transition,
    is_allowed_project_transition,
)
from worker.celery_app import celery_app


_STAGE_MAX_RETRIES = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _seed_for_run(*, pipeline_run_id: str, stage: str, scene_number: int | None = None) -> int:
    base = int(pipeline_run_id.replace("-", "")[:12], 16)
    stage_bias = sum(ord(c) for c in stage) % 10_000
    if scene_number is None:
        return base + stage_bias
    return base + stage_bias + scene_number * 97


def _stage_task_name(stage: str) -> str:
    if stage == PipelineStage.GENERATE_BLUEPRINT:
        return "worker.stage_generate_blueprint"
    if stage == PipelineStage.GENERATE_ASSETS:
        return "worker.stage_generate_assets"
    if stage == PipelineStage.RENDER_ASSEMBLE:
        return "worker.stage_render_assemble"
    raise ValueError(f"Unsupported stage={stage!r}")


def _next_stage(stage: str) -> str | None:
    if stage == PipelineStage.GENERATE_BLUEPRINT:
        return PipelineStage.GENERATE_ASSETS
    if stage == PipelineStage.GENERATE_ASSETS:
        return PipelineStage.RENDER_ASSEMBLE
    if stage == PipelineStage.RENDER_ASSEMBLE:
        return None
    raise ValueError(f"Unsupported stage={stage!r}")


def _enqueue_stage(*, stage: str, project_id: str, pipeline_run_id: str) -> None:
    celery_app.send_task(
        _stage_task_name(stage),
        kwargs={"project_id": project_id, "pipeline_run_id": pipeline_run_id},
    )


def _ensure_project_state(db, *, project: Project, to_state: ProjectState) -> None:
    if project.state == to_state:
        return
    assert_allowed_project_transition(ProjectState(project.state), to_state)
    project.state = to_state
    db.add(project)


def _ensure_stage_run_started(
    db,
    *,
    pipeline_run_id: str,
    stage: str,
) -> tuple[PipelineStageRun, bool]:
    stage_run, _ = claim_pipeline_stage_run(db, pipeline_run_id=pipeline_run_id, stage=stage)
    db.refresh(stage_run)

    if stage_run.status in ("SUCCEEDED", "FAILED"):
        return stage_run, False

    res = db.execute(
        update(PipelineStageRun)
        .where(
            PipelineStageRun.id == stage_run.id,
            PipelineStageRun.status.in_(["PENDING", "RETRYING"]),
        )
        .values(status="RUNNING", started_at=_utcnow(), error_message=None)
    )
    db.commit()
    db.refresh(stage_run)

    return stage_run, res.rowcount == 1


def _mark_stage_succeeded(db, *, stage_run: PipelineStageRun) -> None:
    stage_run.status = "SUCCEEDED"
    stage_run.finished_at = _utcnow()
    stage_run.error_message = None
    db.add(stage_run)
    db.commit()


def _mark_stage_retrying(db, *, stage_run: PipelineStageRun, error_message: str) -> None:
    stage_run.status = "RETRYING"
    stage_run.error_message = error_message[:10_000]
    db.add(stage_run)
    db.commit()


def _mark_pipeline_failed(db, *, project: Project, run: PipelineRun, stage_run: PipelineStageRun, reason: str) -> None:
    stage_run.status = "FAILED"
    stage_run.finished_at = _utcnow()
    stage_run.error_message = reason[:10_000]
    db.add(stage_run)

    if run.status != PipelineRunStatus.FAILED:
        assert_allowed_pipeline_run_transition(PipelineRunStatus(run.status), PipelineRunStatus.FAILED)
        run.status = PipelineRunStatus.FAILED
        run.finished_at = _utcnow()
        run.error_message = reason[:10_000]
        db.add(run)

    if project.state != ProjectState.FAILED and is_allowed_project_transition(ProjectState(project.state), ProjectState.FAILED):
        project.state = ProjectState.FAILED
        db.add(project)

    db.commit()


def _get_or_create_asset(
    db,
    *,
    project_id: str,
    scene_id: str | None,
    asset_type: str,
    provider: str,
    uri: str,
    metadata_json: dict | None,
) -> Asset:
    existing = db.execute(
        select(Asset).where(
            Asset.project_id == project_id,
            Asset.scene_id == scene_id,
            Asset.asset_type == asset_type,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.uri != uri or existing.provider != provider or existing.metadata_json != metadata_json:
            existing.provider = provider
            existing.uri = uri
            existing.metadata_json = metadata_json
            db.add(existing)
        return existing

    asset = Asset(
        project_id=project_id,
        scene_id=scene_id,
        asset_type=asset_type,
        provider=provider,
        uri=uri,
        metadata_json=metadata_json,
    )
    db.add(asset)
    db.flush()
    return asset


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="worker.kickoff_pipeline_run")
def kickoff_pipeline_run(*, project_id: str, pipeline_run_id: str) -> dict:
    with SessionLocal() as db:
        pipeline_run = db.execute(
            select(PipelineRun).where(
                PipelineRun.id == pipeline_run_id,
                PipelineRun.project_id == project_id,
            )
        ).scalar_one_or_none()
        if pipeline_run is None:
            return {"ok": False, "reason": "run_not_found"}

        if pipeline_run.status != PipelineRunStatus.PENDING:
            if pipeline_run.status == PipelineRunStatus.RUNNING and pipeline_run.current_stage is not None:
                _enqueue_stage(stage=pipeline_run.current_stage, project_id=project_id, pipeline_run_id=pipeline_run_id)
            return {"ok": True, "status": pipeline_run.status, "skipped": True}

        assert_allowed_pipeline_run_transition(PipelineRunStatus(pipeline_run.status), PipelineRunStatus.RUNNING)
        pipeline_run.status = PipelineRunStatus.RUNNING
        pipeline_run.current_stage = PipelineStage.GENERATE_BLUEPRINT
        pipeline_run.started_at = _utcnow()
        db.commit()

        claim_pipeline_stage_run(
            db,
            pipeline_run_id=pipeline_run.id,
            stage=PipelineStage.GENERATE_BLUEPRINT,
        )

        _enqueue_stage(stage=PipelineStage.GENERATE_BLUEPRINT, project_id=project_id, pipeline_run_id=pipeline_run_id)
        return {"ok": True, "status": pipeline_run.status, "current_stage": pipeline_run.current_stage}


@celery_app.task(
    name="worker.stage_generate_blueprint",
    bind=True,
    max_retries=_STAGE_MAX_RETRIES,
)
def stage_generate_blueprint(self, *, project_id: str, pipeline_run_id: str) -> dict:
    with SessionLocal() as db:
        pipeline_run = db.execute(
            select(PipelineRun).where(PipelineRun.id == pipeline_run_id, PipelineRun.project_id == project_id)
        ).scalar_one_or_none()
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
        if pipeline_run is None or project is None:
            return {"ok": False, "reason": "not_found"}

        stage_run, started = _ensure_stage_run_started(db, pipeline_run_id=pipeline_run.id, stage=PipelineStage.GENERATE_BLUEPRINT)
        if not started:
            if stage_run.status == "SUCCEEDED":
                next_stage = _next_stage(PipelineStage.GENERATE_BLUEPRINT)
                if next_stage is not None and pipeline_run.status == PipelineRunStatus.RUNNING:
                    _enqueue_stage(stage=next_stage, project_id=project_id, pipeline_run_id=pipeline_run_id)
            return {"ok": True, "stage": stage_run.stage, "status": stage_run.status, "skipped": True}

        try:
            if pipeline_run.current_stage != PipelineStage.GENERATE_BLUEPRINT:
                pipeline_run.current_stage = PipelineStage.GENERATE_BLUEPRINT
                db.add(pipeline_run)

            if project.state in {
                ProjectState.SCRIPT_READY,
                ProjectState.ASSET_GENERATING,
                ProjectState.ASSETS_READY,
                ProjectState.RENDERING,
                ProjectState.COMPLETED,
            }:
                _mark_stage_succeeded(db, stage_run=stage_run)
                pipeline_run.current_stage = PipelineStage.GENERATE_ASSETS
                db.add(pipeline_run)
                db.commit()
                claim_pipeline_stage_run(db, pipeline_run_id=pipeline_run.id, stage=PipelineStage.GENERATE_ASSETS)
                _enqueue_stage(stage=PipelineStage.GENERATE_ASSETS, project_id=project_id, pipeline_run_id=pipeline_run_id)
                return {"ok": True, "stage": stage_run.stage, "status": stage_run.status, "skipped": True}

            _ensure_project_state(db, project=project, to_state=ProjectState.SCRIPTING)
            db.commit()

            providers = get_providers()
            blueprint_dict = providers.llm.generate_blueprint(
                project.topic,
                project.target_duration_seconds,
                seed=_seed_for_run(pipeline_run_id=pipeline_run.id, stage=PipelineStage.GENERATE_BLUEPRINT),
            )
            blueprint = Blueprint.model_validate(blueprint_dict)
            project.blueprint_json = blueprint.model_dump(mode="json")
            db.add(project)

            existing_scenes = (
                db.execute(select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_number)).scalars().all()
            )
            existing_by_number = {s.scene_number: s for s in existing_scenes}
            expected_numbers = {s.scene_number for s in blueprint.scenes}

            for s in blueprint.scenes:
                existing = existing_by_number.get(s.scene_number)
                if existing is None:
                    existing = Scene(
                        project_id=project.id,
                        scene_number=s.scene_number,
                        status="PENDING",
                    )
                    db.add(existing)
                existing.narration_script = s.narration_script
                existing.image_generation_prompt = s.image_generation_prompt
                existing.camera_movement_suggestion = s.camera_movement_suggestion
                existing.estimated_duration_seconds = s.estimated_duration_seconds
                existing.status = "PENDING"
                db.add(existing)

            extra_scene_ids = [s.id for s in existing_scenes if s.scene_number not in expected_numbers]
            if extra_scene_ids:
                db.execute(delete(Asset).where(Asset.scene_id.in_(extra_scene_ids)))
                db.execute(delete(Scene).where(Scene.id.in_(extra_scene_ids)))

            _ensure_project_state(db, project=project, to_state=ProjectState.SCRIPT_READY)
            db.commit()

            _mark_stage_succeeded(db, stage_run=stage_run)

            pipeline_run.current_stage = PipelineStage.GENERATE_ASSETS
            db.add(pipeline_run)
            db.commit()

            claim_pipeline_stage_run(db, pipeline_run_id=pipeline_run.id, stage=PipelineStage.GENERATE_ASSETS)
            _enqueue_stage(stage=PipelineStage.GENERATE_ASSETS, project_id=project_id, pipeline_run_id=pipeline_run_id)
            return {"ok": True, "stage": stage_run.stage, "status": stage_run.status}
        except Exception as exc:
            err = str(exc) or exc.__class__.__name__
            if self.request.retries < _STAGE_MAX_RETRIES:
                _mark_stage_retrying(db, stage_run=stage_run, error_message=err)
                raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))

            _mark_pipeline_failed(db, project=project, run=pipeline_run, stage_run=stage_run, reason=err)
            db.execute(
                update(Scene)
                .where(Scene.project_id == project.id, Scene.status != "READY")
                .values(status="FAILED")
            )
            db.commit()
            return {"ok": False, "stage": stage_run.stage, "status": stage_run.status, "reason": err}


@celery_app.task(
    name="worker.stage_generate_assets",
    bind=True,
    max_retries=_STAGE_MAX_RETRIES,
)
def stage_generate_assets(self, *, project_id: str, pipeline_run_id: str) -> dict:
    with SessionLocal() as db:
        pipeline_run = db.execute(
            select(PipelineRun).where(PipelineRun.id == pipeline_run_id, PipelineRun.project_id == project_id)
        ).scalar_one_or_none()
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
        if pipeline_run is None or project is None:
            return {"ok": False, "reason": "not_found"}

        stage_run, started = _ensure_stage_run_started(db, pipeline_run_id=pipeline_run.id, stage=PipelineStage.GENERATE_ASSETS)
        if not started:
            if stage_run.status == "SUCCEEDED":
                next_stage = _next_stage(PipelineStage.GENERATE_ASSETS)
                if next_stage is not None and pipeline_run.status == PipelineRunStatus.RUNNING:
                    _enqueue_stage(stage=next_stage, project_id=project_id, pipeline_run_id=pipeline_run_id)
            return {"ok": True, "stage": stage_run.stage, "status": stage_run.status, "skipped": True}

        try:
            if pipeline_run.current_stage != PipelineStage.GENERATE_ASSETS:
                pipeline_run.current_stage = PipelineStage.GENERATE_ASSETS
                db.add(pipeline_run)

            if project.state in {
                ProjectState.ASSETS_READY,
                ProjectState.RENDERING,
                ProjectState.COMPLETED,
            }:
                _mark_stage_succeeded(db, stage_run=stage_run)
                pipeline_run.current_stage = PipelineStage.RENDER_ASSEMBLE
                db.add(pipeline_run)
                db.commit()
                claim_pipeline_stage_run(db, pipeline_run_id=pipeline_run.id, stage=PipelineStage.RENDER_ASSEMBLE)
                _enqueue_stage(stage=PipelineStage.RENDER_ASSEMBLE, project_id=project_id, pipeline_run_id=pipeline_run_id)
                return {"ok": True, "stage": stage_run.stage, "status": stage_run.status, "skipped": True}

            _ensure_project_state(db, project=project, to_state=ProjectState.ASSET_GENERATING)
            db.commit()

            providers = get_providers()

            scenes = (
                db.execute(select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_number)).scalars().all()
            )
            if not scenes:
                raise ValueError("No scenes found; cannot generate assets")

            for scene in scenes:
                if scene.image_generation_prompt is None or scene.narration_script is None:
                    raise ValueError(f"Scene {scene.scene_number} missing prompts/scripts")

                image_asset = db.execute(
                    select(Asset).where(
                        Asset.project_id == project.id,
                        Asset.scene_id == scene.id,
                        Asset.asset_type == "image",
                    )
                ).scalar_one_or_none()
                if image_asset is None:
                    generated = providers.text_to_image.generate_image(
                        scene.image_generation_prompt,
                        seed=_seed_for_run(
                            pipeline_run_id=pipeline_run.id,
                            stage=PipelineStage.GENERATE_ASSETS,
                            scene_number=scene.scene_number,
                        ),
                    )
                    image_asset = _get_or_create_asset(
                        db,
                        project_id=project.id,
                        scene_id=scene.id,
                        asset_type="image",
                        provider=generated.provider,
                        uri=generated.uri,
                        metadata_json=generated.metadata,
                    )

                audio_asset = db.execute(
                    select(Asset).where(
                        Asset.project_id == project.id,
                        Asset.scene_id == scene.id,
                        Asset.asset_type == "audio",
                    )
                ).scalar_one_or_none()
                if audio_asset is None:
                    generated = providers.tts.synthesize(
                        scene.narration_script,
                        voice="mock",
                        seed=_seed_for_run(
                            pipeline_run_id=pipeline_run.id,
                            stage=f"{PipelineStage.GENERATE_ASSETS}:audio",
                            scene_number=scene.scene_number,
                        ),
                    )
                    _get_or_create_asset(
                        db,
                        project_id=project.id,
                        scene_id=scene.id,
                        asset_type="audio",
                        provider=generated.provider,
                        uri=generated.uri,
                        metadata_json=generated.metadata,
                    )

                video_asset = db.execute(
                    select(Asset).where(
                        Asset.project_id == project.id,
                        Asset.scene_id == scene.id,
                        Asset.asset_type == "video",
                    )
                ).scalar_one_or_none()
                if video_asset is None:
                    motion_prompt = scene.camera_movement_suggestion or "minimal camera motion"
                    image_uri_for_video = image_asset.uri
                    if providers.image_to_video.provider_name == "pixverse":
                        image_uri_for_video = f"prompt://{quote(scene.image_generation_prompt, safe='')}"
                    generated = providers.image_to_video.generate_video(
                        image_uri_for_video,
                        motion_prompt,
                        seed=_seed_for_run(
                            pipeline_run_id=pipeline_run.id,
                            stage=f"{PipelineStage.GENERATE_ASSETS}:video",
                            scene_number=scene.scene_number,
                        ),
                    )
                    _get_or_create_asset(
                        db,
                        project_id=project.id,
                        scene_id=scene.id,
                        asset_type="video",
                        provider=generated.provider,
                        uri=generated.uri,
                        metadata_json=generated.metadata,
                    )

                scene.status = "READY"
                db.add(scene)

            _ensure_project_state(db, project=project, to_state=ProjectState.ASSETS_READY)
            db.commit()

            _mark_stage_succeeded(db, stage_run=stage_run)

            pipeline_run.current_stage = PipelineStage.RENDER_ASSEMBLE
            db.add(pipeline_run)
            db.commit()

            claim_pipeline_stage_run(db, pipeline_run_id=pipeline_run.id, stage=PipelineStage.RENDER_ASSEMBLE)
            _enqueue_stage(stage=PipelineStage.RENDER_ASSEMBLE, project_id=project_id, pipeline_run_id=pipeline_run_id)
            return {"ok": True, "stage": stage_run.stage, "status": stage_run.status}
        except Exception as exc:
            err = str(exc) or exc.__class__.__name__
            if self.request.retries < _STAGE_MAX_RETRIES:
                _mark_stage_retrying(db, stage_run=stage_run, error_message=err)
                raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))

            _mark_pipeline_failed(db, project=project, run=pipeline_run, stage_run=stage_run, reason=err)
            db.execute(
                update(Scene)
                .where(Scene.project_id == project.id, Scene.status != "READY")
                .values(status="FAILED")
            )
            db.commit()
            return {"ok": False, "stage": stage_run.stage, "status": stage_run.status, "reason": err}


@celery_app.task(
    name="worker.stage_render_assemble",
    bind=True,
    max_retries=_STAGE_MAX_RETRIES,
)
def stage_render_assemble(self, *, project_id: str, pipeline_run_id: str) -> dict:
    with SessionLocal() as db:
        pipeline_run = db.execute(
            select(PipelineRun).where(PipelineRun.id == pipeline_run_id, PipelineRun.project_id == project_id)
        ).scalar_one_or_none()
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
        if pipeline_run is None or project is None:
            return {"ok": False, "reason": "not_found"}

        stage_run, started = _ensure_stage_run_started(db, pipeline_run_id=pipeline_run.id, stage=PipelineStage.RENDER_ASSEMBLE)
        if not started:
            return {"ok": True, "stage": stage_run.stage, "status": stage_run.status, "skipped": True}

        try:
            if pipeline_run.current_stage != PipelineStage.RENDER_ASSEMBLE:
                pipeline_run.current_stage = PipelineStage.RENDER_ASSEMBLE
                db.add(pipeline_run)

            if project.state == ProjectState.COMPLETED and pipeline_run.status == PipelineRunStatus.SUCCEEDED:
                _mark_stage_succeeded(db, stage_run=stage_run)
                return {"ok": True, "stage": stage_run.stage, "status": stage_run.status, "skipped": True}

            _ensure_project_state(db, project=project, to_state=ProjectState.RENDERING)
            db.commit()

            existing_final = db.execute(
                select(Asset).where(
                    Asset.project_id == project.id,
                    Asset.scene_id.is_(None),
                    Asset.asset_type == "final_mp4",
                )
            ).scalar_one_or_none()
            if existing_final is not None and existing_final.uri:
                _ensure_project_state(db, project=project, to_state=ProjectState.COMPLETED)
                db.commit()
            else:
                settings = get_settings()
                output_format = os.getenv("VIDEOSUP_OUTPUT_FORMAT", "mp4").strip().lower()
                render_profile = os.getenv("VIDEOSUP_RENDER_PROFILE", "final").strip().lower()

                scenes = (
                    db.execute(select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_number))
                    .scalars()
                    .all()
                )
                if not scenes:
                    raise ValueError("No scenes found; cannot render assemble")

                job_scenes: list[dict] = []
                for s in scenes:
                    v = db.execute(
                        select(Asset).where(
                            Asset.project_id == project.id,
                            Asset.scene_id == s.id,
                            Asset.asset_type == "video",
                        )
                    ).scalar_one_or_none()
                    if v is None:
                        raise ValueError(f"Missing video asset for scene {s.scene_number}")
                    job_scenes.append(
                        {
                            "scene_id": s.id,
                            "clip_url": v.uri,
                            "prompt": s.image_generation_prompt or "",
                            "expected_duration_ms": int((s.estimated_duration_seconds or 5) * 1000),
                        }
                    )

                voiceover_script = "\n\n".join((s.narration_script or "").strip() for s in scenes).strip()
                if not voiceover_script:
                    voiceover_script = " "

                job_payload = {
                    "schema_version": "1.0.0",
                    "project_id": project.id,
                    "pipeline_run_id": pipeline_run.id,
                    "render_profile": "preview" if render_profile == "preview" else "final",
                    "output_format": "hls" if output_format == "hls" else "mp4",
                    "scenes": job_scenes,
                    "voiceover_script": voiceover_script,
                    "subtitle_style": {
                        "preset": os.getenv("VIDEOSUP_SUBTITLE_PRESET", "tiktok_bounce"),
                        "language": os.getenv("VIDEOSUP_SUBTITLE_LANGUAGE", "en"),
                        "max_chars_per_line": int(os.getenv("VIDEOSUP_SUBTITLE_MAX_CHARS", "26")),
                        "safe_area_pct": float(os.getenv("VIDEOSUP_SUBTITLE_SAFE_AREA", "0.12")),
                    },
                }

                with httpx.Client(timeout=30.0) as client:
                    submit = client.post(f"{settings.videosup_base_url}/jobs", json=job_payload)
                    submit.raise_for_status()
                    job_id = submit.json().get("job_id")
                    if not job_id:
                        raise ValueError("VideoSup did not return job_id")

                    deadline = time.monotonic() + settings.videosup_max_poll_sec
                    while time.monotonic() < deadline:
                        poll = client.get(f"{settings.videosup_base_url}/jobs/{job_id}")
                        poll.raise_for_status()
                        body = poll.json()
                        state = body.get("state") or {}
                        status = state.get("status")
                        if status == "succeeded":
                            outputs = body.get("outputs") or {}
                            mp4_url = outputs.get("mp4_url")
                            hls_master_url = outputs.get("hls_master_url")
                            if mp4_url:
                                _get_or_create_asset(
                                    db,
                                    project_id=project.id,
                                    scene_id=None,
                                    asset_type="final_mp4",
                                    provider="videosup",
                                    uri=str(mp4_url),
                                    metadata_json={"videosup_job_id": job_id},
                                )
                            if hls_master_url:
                                _get_or_create_asset(
                                    db,
                                    project_id=project.id,
                                    scene_id=None,
                                    asset_type="hls_master",
                                    provider="videosup",
                                    uri=str(hls_master_url),
                                    metadata_json={"videosup_job_id": job_id},
                                )
                            db.commit()
                            _ensure_project_state(db, project=project, to_state=ProjectState.COMPLETED)
                            db.commit()
                            break
                        if status == "failed":
                            err_obj = state.get("error") or {}
                            raise RuntimeError(str(err_obj.get("message") or "VideoSup failed"))
                        time.sleep(settings.videosup_poll_interval_sec)
                    else:
                        raise TimeoutError("VideoSup job polling timed out")

            _mark_stage_succeeded(db, stage_run=stage_run)

            if pipeline_run.status != PipelineRunStatus.SUCCEEDED:
                assert_allowed_pipeline_run_transition(PipelineRunStatus(pipeline_run.status), PipelineRunStatus.SUCCEEDED)
                pipeline_run.status = PipelineRunStatus.SUCCEEDED
                pipeline_run.finished_at = _utcnow()
                pipeline_run.error_message = None
                pipeline_run.current_stage = None
                db.add(pipeline_run)
                db.commit()

            return {"ok": True, "stage": stage_run.stage, "status": stage_run.status}
        except Exception as exc:
            err = str(exc) or exc.__class__.__name__
            if self.request.retries < _STAGE_MAX_RETRIES:
                _mark_stage_retrying(db, stage_run=stage_run, error_message=err)
                raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))

            _mark_pipeline_failed(db, project=project, run=pipeline_run, stage_run=stage_run, reason=err)
            db.execute(
                update(Scene)
                .where(Scene.project_id == project.id, Scene.status != "READY")
                .values(status="FAILED")
            )
            db.commit()
            return {"ok": False, "stage": stage_run.stage, "status": stage_run.status, "reason": err}
