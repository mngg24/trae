from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..logging_utils import log_event
from .ffmpeg import run_ffmpeg


@dataclass(frozen=True)
class PackagingConfig:
    segment_duration_sec: int = 4
    ffmpeg_timeout_sec: float = 20 * 60


@dataclass(frozen=True)
class PackageResult:
    mp4_path: Path
    hls_master_path: Optional[Path] = None
    hls_dir: Optional[Path] = None


class Packager:
    def __init__(
        self, *, config: PackagingConfig, logger: Optional[logging.Logger] = None
    ):
        self._cfg = config
        self._logger = logger or logging.getLogger("videosup.packager")

    def package_mp4(
        self,
        *,
        job_id: str,
        input_path: Path,
        subtitle_ass_path: Optional[Path],
        out_path: Path,
        render_profile: str,
    ) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = out_path.with_suffix(".tmp" + out_path.suffix)

        argv = ["ffmpeg", "-y", "-i", str(input_path)]
        if subtitle_ass_path is not None:
            argv += ["-vf", _ass_filter(subtitle_ass_path)]
        argv += [
            "-f",
            "mp4",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast" if render_profile == "preview" else "fast",
            "-crf",
            "28" if render_profile == "preview" else "22",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(tmp_path),
        ]

        log_event(
            self._logger,
            job_id=job_id,
            step="package",
            message="mp4_start",
            output=str(out_path),
        )
        run_ffmpeg(
            job_id=job_id,
            step="package",
            logger=self._logger,
            argv=argv,
            timeout_sec=self._cfg.ffmpeg_timeout_sec,
        )
        os.replace(tmp_path, out_path)
        return out_path

    def package_hls_abr(
        self,
        *,
        job_id: str,
        input_path: Path,
        subtitle_ass_path: Optional[Path],
        out_dir: Path,
        render_profile: str,
    ) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        master = out_dir / "master.m3u8"

        v0_bitrate = "700k" if render_profile == "preview" else "900k"
        v1_bitrate = "1800k" if render_profile == "preview" else "2500k"
        preset = "veryfast" if render_profile == "preview" else "fast"

        vf_sub = (
            f",{_ass_filter_expr(subtitle_ass_path)}"
            if subtitle_ass_path is not None
            else ""
        )
        filter_complex = (
            f"[0:v]split=2[v1][v2];"
            f"[v1]scale=-2:360{vf_sub}[v360];"
            f"[v2]scale=-2:720{vf_sub}[v720]"
        )

        argv = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v360]",
            "-map",
            "0:a:0",
            "-map",
            "[v720]",
            "-map",
            "0:a:0",
            "-c:v:0",
            "libx264",
            "-b:v:0",
            v0_bitrate,
            "-preset",
            preset,
            "-g",
            "60",
            "-keyint_min",
            "60",
            "-sc_threshold",
            "0",
            "-c:v:1",
            "libx264",
            "-b:v:1",
            v1_bitrate,
            "-preset",
            preset,
            "-g",
            "60",
            "-keyint_min",
            "60",
            "-sc_threshold",
            "0",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-f",
            "hls",
            "-hls_time",
            str(self._cfg.segment_duration_sec),
            "-hls_playlist_type",
            "vod",
            "-master_pl_name",
            master.name,
            "-var_stream_map",
            "v:0,a:0 v:1,a:1",
            "-hls_segment_filename",
            str(out_dir / "v%v_seg_%03d.ts"),
            str(out_dir / "v%v.m3u8"),
        ]

        log_event(
            self._logger,
            job_id=job_id,
            step="package",
            message="hls_start",
            out_dir=str(out_dir),
        )
        run_ffmpeg(
            job_id=job_id,
            step="package",
            logger=self._logger,
            argv=argv,
            timeout_sec=self._cfg.ffmpeg_timeout_sec,
        )
        return master


def _ffmpeg_path(p: Path) -> str:
    return str(p).replace("\\", "/")


def _ass_filter(p: Path) -> str:
    path = _ffmpeg_path(p)
    path = path.replace(":", "\\:")
    path = path.replace("'", "\\'")
    return f"ass='{path}'"


def _ass_filter_expr(p: Path) -> str:
    return _ass_filter(p)
