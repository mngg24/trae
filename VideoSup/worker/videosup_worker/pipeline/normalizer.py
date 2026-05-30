from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from ..logging_utils import log_event
from ..fetcher.errors import ErrorDescriptor, ErrorStrategy, ErrorTaxonomy, FetcherError
from .ffmpeg import ffprobe_media, is_close, run_ffmpeg


@dataclass(frozen=True)
class NormalizeConfig:
    target_height: int = 720
    target_fps: int = 30
    v_codec: str = "h264"
    a_codec: str = "aac"
    timeout_sec: float = 5 * 60


@dataclass(frozen=True)
class NormalizeResult:
    path: Path
    fast_path: bool


class Normalizer:
    def __init__(
        self, *, config: NormalizeConfig, logger: Optional[logging.Logger] = None
    ):
        self._cfg = config
        self._logger = logger or logging.getLogger("videosup.normalizer")

    def normalize_one(
        self, *, job_id: str, input_path: Path, out_dir: Path
    ) -> NormalizeResult:
        if not input_path.exists():
            raise FetcherError(
                ErrorDescriptor(
                    code=ErrorTaxonomy.BAD_MEDIA,
                    message="Input file not found",
                    strategy=ErrorStrategy.ABORT,
                ),
                details=str(input_path),
            )

        info = ffprobe_media(
            job_id=job_id, step="normalize_probe", logger=self._logger, path=input_path
        )
        if not info.has_video:
            raise FetcherError(
                ErrorDescriptor(
                    code=ErrorTaxonomy.BAD_MEDIA,
                    message="No video stream",
                    strategy=ErrorStrategy.ABORT,
                )
            )

        if self._is_fast_path(info):
            log_event(
                self._logger,
                job_id=job_id,
                step="normalize",
                message="fast_path",
                input=str(input_path),
            )
            return NormalizeResult(path=input_path, fast_path=True)

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{input_path.stem}.norm.mp4"
        tmp_path = out_dir / f"{input_path.stem}.norm.tmp.mp4"

        argv, needs_silence = self._build_ffmpeg_args(
            input_path=input_path, output_path=tmp_path, has_audio=info.has_audio
        )
        log_event(
            self._logger,
            job_id=job_id,
            step="normalize",
            message="transcode_start",
            input=str(input_path),
            output=str(out_path),
            add_silence=needs_silence,
        )
        run_ffmpeg(
            job_id=job_id,
            step="normalize",
            logger=self._logger,
            argv=argv,
            timeout_sec=self._cfg.timeout_sec,
        )
        os.replace(tmp_path, out_path)
        return NormalizeResult(path=out_path, fast_path=False)

    def _is_fast_path(self, info) -> bool:
        if info.v_codec != self._cfg.v_codec:
            return False
        if info.a_codec != self._cfg.a_codec:
            return False
        if info.height != self._cfg.target_height:
            return False
        if not is_close(info.avg_fps, float(self._cfg.target_fps), tol=0.05):
            return False
        return True

    def _build_ffmpeg_args(
        self, *, input_path: Path, output_path: Path, has_audio: bool
    ) -> Tuple[list[str], bool]:
        vf = f"scale=-2:{self._cfg.target_height},fps={self._cfg.target_fps}"
        argv = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
        ]
        needs_silence = False
        if not has_audio:
            needs_silence = True
            argv += [
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
        argv += [
            "-vf",
            vf,
        ]
        if has_audio:
            argv += ["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"]
        else:
            argv += [
                "-shortest",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ar",
                "48000",
                "-ac",
                "2",
            ]

        argv += [
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        return argv, needs_silence
