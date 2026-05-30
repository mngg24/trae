from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from ..logging_utils import log_event
from .ffmpeg import ffprobe_media, run_ffmpeg


@dataclass(frozen=True)
class ComposeConfig:
    loudness_normalize: bool = True
    max_sync_pad_sec: float = 30.0
    ffmpeg_timeout_sec: float = 10 * 60


@dataclass(frozen=True)
class ComposePlan:
    concat_list_path: Path
    video_duration_sec: float


class Composer:
    def __init__(
        self, *, config: ComposeConfig, logger: Optional[logging.Logger] = None
    ):
        self._cfg = config
        self._logger = logger or logging.getLogger("videosup.composer")

    def build_concat_list(
        self, *, job_id: str, clip_paths: List[Path], out_dir: Path
    ) -> ComposePlan:
        out_dir.mkdir(parents=True, exist_ok=True)
        concat_list = out_dir / "concat.txt"
        lines: List[str] = []
        video_dur = 0.0
        for p in clip_paths:
            info = ffprobe_media(
                job_id=job_id, step="compose_probe", logger=self._logger, path=p
            )
            if info.duration_sec is not None:
                video_dur += float(info.duration_sec)
            lines.append(f"file '{_escape_concat_path(p)}'")
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log_event(
            self._logger,
            job_id=job_id,
            step="compose",
            message="concat_list_built",
            clip_count=len(clip_paths),
            video_duration_sec=round(video_dur, 3),
            concat_list=str(concat_list),
        )
        return ComposePlan(concat_list_path=concat_list, video_duration_sec=video_dur)

    def render_base_with_voiceover(
        self,
        *,
        job_id: str,
        concat_list_path: Path,
        voiceover_audio_path: Path,
        out_path_tmp: Path,
        target_duration_sec: float,
        render_profile: str,
    ) -> None:
        out_path_tmp.parent.mkdir(parents=True, exist_ok=True)
        audio_info = ffprobe_media(
            job_id=job_id,
            step="compose_audio_probe",
            logger=self._logger,
            path=voiceover_audio_path,
        )
        audio_dur = float(audio_info.duration_sec or 0.0)

        vf, af, out_dur = self._build_sync_filters(
            video_duration_sec=target_duration_sec,
            audio_duration_sec=audio_dur,
        )

        if self._cfg.loudness_normalize and render_profile == "final":
            af = f"{af},loudnorm=I=-16:TP=-1.5:LRA=11"

        argv = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-i",
            str(voiceover_audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            vf,
            "-af",
            af,
            "-t",
            f"{out_dur:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast" if render_profile == "preview" else "fast",
            "-crf",
            "28" if render_profile == "preview" else "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(out_path_tmp),
        ]

        log_event(
            self._logger,
            job_id=job_id,
            step="compose",
            message="compose_start",
            out_duration_sec=round(out_dur, 3),
        )
        run_ffmpeg(
            job_id=job_id,
            step="compose",
            logger=self._logger,
            argv=argv,
            timeout_sec=self._cfg.ffmpeg_timeout_sec,
        )

    def _build_sync_filters(
        self, *, video_duration_sec: float, audio_duration_sec: float
    ) -> Tuple[str, str, float]:
        video_dur = max(0.0, float(video_duration_sec))
        audio_dur = max(0.0, float(audio_duration_sec))
        if audio_dur <= 0.0:
            audio_dur = video_dur

        if audio_dur > video_dur:
            pad = min(audio_dur - video_dur, self._cfg.max_sync_pad_sec)
            vf = f"tpad=stop_mode=clone:stop_duration={pad:.3f}"
            af = "anull"
            out_dur = video_dur + pad
        else:
            vf = "null"
            af = "apad"
            out_dur = video_dur

        return vf, af, out_dur


def _escape_concat_path(p: Path) -> str:
    s = str(p).replace("\\", "/")
    return s.replace("'", "'\\''")
