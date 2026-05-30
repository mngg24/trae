from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional


SchemaVersion = str
RenderProfile = Literal["preview", "final"]
OutputFormat = Literal["mp4", "hls"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]
ProgressStep = Literal["download", "normalize", "compose", "package", "upload"]


class MediaJobValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Scene:
    scene_id: str
    clip_url: str
    prompt: str
    expected_duration_ms: int


@dataclass(frozen=True)
class SubtitleStyle:
    preset: str
    language: Optional[str] = None
    max_chars_per_line: Optional[int] = None
    safe_area_pct: Optional[float] = None


@dataclass(frozen=True)
class Progress:
    step: ProgressStep
    pct: int
    detail: Optional[str] = None


@dataclass(frozen=True)
class ErrorInfo:
    code: str
    message: str
    strategy: Literal["retry", "abort"]


@dataclass(frozen=True)
class JobState:
    status: JobStatus
    progress: Optional[Progress] = None
    error: Optional[ErrorInfo] = None


@dataclass(frozen=True)
class MediaJobSpec:
    schema_version: SchemaVersion
    job_id: str
    project_id: str
    created_at: str
    render_profile: RenderProfile
    output_format: OutputFormat
    scenes: tuple[Scene, ...]
    voiceover_script: str
    subtitle_style: SubtitleStyle
    state: JobState


def _require_str(obj: dict[str, Any], key: str) -> str:
    if key not in obj:
        raise MediaJobValidationError(f"Missing required field: {key}")
    v = obj[key]
    if not isinstance(v, str) or not v:
        raise MediaJobValidationError(f"Field '{key}' must be a non-empty string")
    return v


def _require_int(
    obj: dict[str, Any], key: str, *, min_value: Optional[int] = None
) -> int:
    if key not in obj:
        raise MediaJobValidationError(f"Missing required field: {key}")
    v = obj[key]
    if not isinstance(v, int):
        raise MediaJobValidationError(f"Field '{key}' must be an integer")
    if min_value is not None and v < min_value:
        raise MediaJobValidationError(f"Field '{key}' must be >= {min_value}")
    return v


def validate_media_job_spec(data: dict[str, Any]) -> MediaJobSpec:
    if not isinstance(data, dict):
        raise MediaJobValidationError("Job spec must be a JSON object")

    schema_version = _require_str(data, "schema_version")
    job_id = _require_str(data, "job_id")
    project_id = _require_str(data, "project_id")
    created_at = _require_str(data, "created_at")

    render_profile = _require_str(data, "render_profile")
    if render_profile not in ("preview", "final"):
        raise MediaJobValidationError("render_profile must be 'preview' or 'final'")

    output_format = _require_str(data, "output_format")
    if output_format not in ("mp4", "hls"):
        raise MediaJobValidationError("output_format must be 'mp4' or 'hls'")

    scenes_raw = data.get("scenes")
    if not isinstance(scenes_raw, list) or not scenes_raw:
        raise MediaJobValidationError("scenes must be a non-empty array")

    scenes: list[Scene] = []
    for idx, s in enumerate(scenes_raw):
        if not isinstance(s, dict):
            raise MediaJobValidationError(f"scenes[{idx}] must be an object")
        scenes.append(
            Scene(
                scene_id=_require_str(s, "scene_id"),
                clip_url=_require_str(s, "clip_url"),
                prompt=str(s.get("prompt", "")),
                expected_duration_ms=_require_int(
                    s, "expected_duration_ms", min_value=0
                ),
            )
        )

    voiceover_script = _require_str(data, "voiceover_script")

    subtitle_raw = data.get("subtitle_style")
    if not isinstance(subtitle_raw, dict):
        raise MediaJobValidationError("subtitle_style must be an object")
    preset = _require_str(subtitle_raw, "preset")
    language = subtitle_raw.get("language")
    if language is not None and not isinstance(language, str):
        raise MediaJobValidationError("subtitle_style.language must be a string")
    max_chars = subtitle_raw.get("max_chars_per_line")
    if max_chars is not None:
        if not isinstance(max_chars, int) or max_chars < 10:
            raise MediaJobValidationError(
                "subtitle_style.max_chars_per_line must be int >= 10"
            )
    safe_area = subtitle_raw.get("safe_area_pct")
    if safe_area is not None:
        if not isinstance(safe_area, (int, float)) or safe_area < 0 or safe_area > 0.5:
            raise MediaJobValidationError(
                "subtitle_style.safe_area_pct must be between 0 and 0.5"
            )

    subtitle_style = SubtitleStyle(
        preset=preset,
        language=language,
        max_chars_per_line=max_chars,
        safe_area_pct=float(safe_area) if safe_area is not None else None,
    )

    state_raw = data.get("state")
    if not isinstance(state_raw, dict):
        raise MediaJobValidationError("state must be an object")
    status = _require_str(state_raw, "status")
    if status not in ("queued", "running", "succeeded", "failed", "canceled"):
        raise MediaJobValidationError("state.status is invalid")

    progress = None
    if "progress" in state_raw:
        pr = state_raw["progress"]
        if not isinstance(pr, dict):
            raise MediaJobValidationError("state.progress must be an object")
        step = _require_str(pr, "step")
        if step not in ("download", "normalize", "compose", "package", "upload"):
            raise MediaJobValidationError("state.progress.step is invalid")
        pct = _require_int(pr, "pct", min_value=0)
        if pct > 100:
            raise MediaJobValidationError("state.progress.pct must be <= 100")
        detail = pr.get("detail")
        if detail is not None and not isinstance(detail, str):
            raise MediaJobValidationError("state.progress.detail must be a string")
        progress = Progress(step=step, pct=pct, detail=detail)

    if status == "running" and progress is None:
        raise MediaJobValidationError(
            "state.progress is required when state.status is 'running'"
        )

    error = None
    if "error" in state_raw:
        er = state_raw["error"]
        if not isinstance(er, dict):
            raise MediaJobValidationError("state.error must be an object")
        code = _require_str(er, "code")
        message = _require_str(er, "message")
        strategy = _require_str(er, "strategy")
        if strategy not in ("retry", "abort"):
            raise MediaJobValidationError(
                "state.error.strategy must be 'retry' or 'abort'"
            )
        error = ErrorInfo(code=code, message=message, strategy=strategy)

    if status == "failed" and error is None:
        raise MediaJobValidationError(
            "state.error is required when state.status is 'failed'"
        )

    state = JobState(status=status, progress=progress, error=error)

    return MediaJobSpec(
        schema_version=schema_version,
        job_id=job_id,
        project_id=project_id,
        created_at=created_at,
        render_profile=render_profile,  # type: ignore[arg-type]
        output_format=output_format,  # type: ignore[arg-type]
        scenes=tuple(scenes),
        voiceover_script=voiceover_script,
        subtitle_style=subtitle_style,
        state=state,
    )
