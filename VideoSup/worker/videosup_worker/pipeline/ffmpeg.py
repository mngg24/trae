from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from ..logging_utils import log_event
from ..fetcher.errors import ErrorDescriptor, ErrorStrategy, ErrorTaxonomy, FetcherError


@dataclass(frozen=True)
class MediaInfo:
    has_video: bool
    has_audio: bool
    v_codec: Optional[str]
    a_codec: Optional[str]
    width: Optional[int]
    height: Optional[int]
    avg_fps: Optional[float]
    duration_sec: Optional[float]


def ensure_tools() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found in PATH")
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe not found in PATH")


def _run_cmd(
    *,
    job_id: str,
    step: str,
    logger: logging.Logger,
    argv: List[str],
    timeout_sec: Optional[float] = None,
    stderr_tail_chars: int = 8000,
) -> Tuple[int, str, str]:
    start = time.perf_counter()
    p = subprocess.run(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_sec,
    )
    dur_ms = int((time.perf_counter() - start) * 1000)
    stdout = p.stdout or ""
    stderr = p.stderr or ""
    tail = stderr[-stderr_tail_chars:] if stderr_tail_chars > 0 else ""
    log_event(
        logger,
        job_id=job_id,
        step=step,
        duration_ms=dur_ms,
        message="cmd_done",
        cmd=argv[0],
        exit_code=p.returncode,
    )
    return p.returncode, stdout, tail


def run_ffmpeg(
    *,
    job_id: str,
    step: str,
    logger: logging.Logger,
    argv: List[str],
    timeout_sec: Optional[float] = None,
    stderr_tail_chars: int = 8000,
) -> None:
    ensure_tools()
    exit_code, _stdout, tail = _run_cmd(
        job_id=job_id,
        step=step,
        logger=logger,
        argv=argv,
        timeout_sec=timeout_sec,
        stderr_tail_chars=stderr_tail_chars,
    )
    if exit_code != 0:
        log_event(
            logger,
            level=logging.ERROR,
            job_id=job_id,
            step=step,
            message="ffmpeg_failed",
            stderr_tail=tail,
        )
        raise FetcherError(
            ErrorDescriptor(
                code=ErrorTaxonomy.FFMPEG_FAILED,
                message="FFmpeg failed",
                strategy=ErrorStrategy.ABORT,
            ),
            details=tail,
        )


def ffprobe_media(
    *,
    job_id: str,
    step: str,
    logger: logging.Logger,
    path: Path,
) -> MediaInfo:
    ensure_tools()
    argv = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    exit_code, stdout, tail = _run_cmd(
        job_id=job_id, step=step, logger=logger, argv=argv, timeout_sec=30
    )
    if exit_code != 0:
        raise FetcherError(
            ErrorDescriptor(
                code=ErrorTaxonomy.BAD_MEDIA,
                message="ffprobe failed",
                strategy=ErrorStrategy.ABORT,
            ),
            details=tail,
        )

    try:
        raw = json.loads(stdout)
    except Exception as e:
        raise FetcherError(
            ErrorDescriptor(
                code=ErrorTaxonomy.BAD_MEDIA,
                message="ffprobe output parse failed",
                strategy=ErrorStrategy.ABORT,
            ),
            details=str(e),
        )

    streams = raw.get("streams") if isinstance(raw, dict) else None
    fmt = raw.get("format") if isinstance(raw, dict) else None
    if not isinstance(streams, list):
        streams = []

    has_video = False
    has_audio = False
    v_codec = None
    a_codec = None
    width = None
    height = None
    avg_fps = None
    for s in streams:
        if not isinstance(s, dict):
            continue
        codec_type = s.get("codec_type")
        if codec_type == "video" and not has_video:
            has_video = True
            v_codec = s.get("codec_name")
            width = s.get("width")
            height = s.get("height")
            afr = s.get("avg_frame_rate")
            avg_fps = _parse_fps(afr)
        elif codec_type == "audio" and not has_audio:
            has_audio = True
            a_codec = s.get("codec_name")

    duration_sec = None
    if isinstance(fmt, dict):
        d = fmt.get("duration")
        try:
            if d is not None:
                duration_sec = float(d)
        except Exception:
            duration_sec = None

    return MediaInfo(
        has_video=has_video,
        has_audio=has_audio,
        v_codec=v_codec if isinstance(v_codec, str) else None,
        a_codec=a_codec if isinstance(a_codec, str) else None,
        width=width if isinstance(width, int) else None,
        height=height if isinstance(height, int) else None,
        avg_fps=avg_fps,
        duration_sec=duration_sec,
    )


def _parse_fps(v: Any) -> Optional[float]:
    if not isinstance(v, str) or not v or v == "0/0":
        return None
    if "/" in v:
        num, den = v.split("/", 1)
        try:
            n = float(num)
            d = float(den)
            if d == 0:
                return None
            return n / d
        except Exception:
            return None
    try:
        return float(v)
    except Exception:
        return None


def is_close(a: Optional[float], b: float, *, tol: float) -> bool:
    if a is None:
        return False
    return abs(a - b) <= tol
