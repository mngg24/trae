from __future__ import annotations

import logging
import os
import random
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logging_utils import log_event
from ..contracts.media_job_spec import MediaJobSpec
from ..storage import StorageManager
from .cache_manager import CacheManager
from .composer import Composer, ComposeConfig
from .ffmpeg import ffprobe_media
from .normalizer import NormalizeConfig, Normalizer
from .packager import Packager, PackagingConfig
from .subtitles import SubtitleConfig, SubtitleGenerator


PIPELINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class PipelineConfig:
    work_dir: Path = Path(".work/videosup")
    cache_dir: Path = Path(".cache/videosup/render")
    duration_tolerance_sec: float = 0.35


@dataclass(frozen=True)
class PipelineResult:
    cache_hit: bool
    content_hash: str
    mp4_path: Optional[Path] = None
    mp4_url: Optional[str] = None
    hls_master_path: Optional[Path] = None
    hls_master_url: Optional[str] = None
    upload_status: Optional[str] = None
    upload_error: Optional[str] = None


class Pipeline:
    def __init__(
        self, *, config: PipelineConfig, logger: Optional[logging.Logger] = None
    ):
        self._cfg = config
        self._logger = logger or logging.getLogger("videosup.pipeline")
        self._cfg.work_dir.mkdir(parents=True, exist_ok=True)
        self._cache = CacheManager(
            cache_dir=self._cfg.cache_dir, logger=logging.getLogger("videosup.cache")
        )
        self._storage = StorageManager.from_env(
            logger=logging.getLogger("videosup.storage")
        )
        self._normalizer = Normalizer(
            config=NormalizeConfig(), logger=logging.getLogger("videosup.normalizer")
        )
        self._composer = Composer(
            config=ComposeConfig(), logger=logging.getLogger("videosup.composer")
        )
        self._subs = SubtitleGenerator(
            config=SubtitleConfig(), logger=logging.getLogger("videosup.subtitles")
        )
        self._packager = Packager(
            config=PackagingConfig(), logger=logging.getLogger("videosup.packager")
        )

    def run(
        self,
        *,
        job_id: str,
        spec: MediaJobSpec,
        clip_paths: List[Path],
        voiceover_audio_path: Path,
    ) -> PipelineResult:
        payload = _cache_payload(spec)
        cache_res = self._cache.cache_lookup(job_id=job_id, payload=payload)
        if cache_res.hit and (
            cache_res.mp4_path is not None or cache_res.mp4_url is not None
        ):
            return PipelineResult(
                cache_hit=True,
                content_hash=cache_res.content_hash,
                mp4_path=cache_res.mp4_path,
                mp4_url=cache_res.mp4_url,
                hls_master_path=cache_res.hls_master_path,
                hls_master_url=cache_res.hls_master_url,
                upload_status="cached",
            )

        paths = self._cache.cache_paths(content_hash=cache_res.content_hash)
        mp4_out = paths["mp4"]
        hls_dir = paths["hls_dir"]
        hls_master = paths["hls_master"]

        tmp_root = (
            self._cfg.work_dir
            / f"{job_id}.{int(time.time())}.{random.randint(1000, 9999)}"
        )
        tmp_root.mkdir(parents=True, exist_ok=True)
        try:
            return self._run_uncached(
                job_id=job_id,
                spec=spec,
                clip_paths=clip_paths,
                voiceover_audio_path=voiceover_audio_path,
                tmp_root=tmp_root,
                content_hash=cache_res.content_hash,
                mp4_out=mp4_out,
                hls_dir=hls_dir,
                hls_master=hls_master,
            )
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def _run_uncached(
        self,
        *,
        job_id: str,
        spec: MediaJobSpec,
        clip_paths: List[Path],
        voiceover_audio_path: Path,
        tmp_root: Path,
        content_hash: str,
        mp4_out: Path,
        hls_dir: Path,
        hls_master: Path,
    ) -> PipelineResult:
        log_event(
            self._logger,
            job_id=job_id,
            step="pipeline",
            message="start",
            content_hash=content_hash,
        )

        norm_dir = tmp_root / "normalized"
        norm_paths: List[Path] = []
        for p in clip_paths:
            r = self._normalizer.normalize_one(
                job_id=job_id, input_path=p, out_dir=norm_dir
            )
            norm_paths.append(r.path)

        compose_dir = tmp_root / "compose"
        plan = self._composer.build_concat_list(
            job_id=job_id, clip_paths=norm_paths, out_dir=compose_dir
        )

        base_tmp = compose_dir / "base.tmp.mp4"
        base_mp4 = compose_dir / "base.mp4"
        self._composer.render_base_with_voiceover(
            job_id=job_id,
            concat_list_path=plan.concat_list_path,
            voiceover_audio_path=voiceover_audio_path,
            out_path_tmp=base_tmp,
            target_duration_sec=plan.video_duration_sec,
            render_profile=spec.render_profile,
        )
        os.replace(base_tmp, base_mp4)

        base_info = ffprobe_media(
            job_id=job_id, step="probe_base", logger=self._logger, path=base_mp4
        )
        base_dur = float(base_info.duration_sec or 0.0)
        sub_dir = tmp_root / "subtitles"
        ass_path = sub_dir / "sub.ass"

        safe_area = (
            spec.subtitle_style.safe_area_pct
            if spec.subtitle_style.safe_area_pct is not None
            else 0.12
        )
        max_chars = (
            spec.subtitle_style.max_chars_per_line
            if spec.subtitle_style.max_chars_per_line is not None
            else 26
        )
        self._subs.generate_ass(
            job_id=job_id,
            voiceover_script=spec.voiceover_script,
            duration_sec=base_dur,
            preset=spec.subtitle_style.preset,
            render_profile=spec.render_profile,
            max_chars_per_line=max_chars,
            safe_area_pct=safe_area,
            out_path=ass_path,
        )

        mp4_out.parent.mkdir(parents=True, exist_ok=True)
        packaged_mp4 = self._packager.package_mp4(
            job_id=job_id,
            input_path=base_mp4,
            subtitle_ass_path=ass_path,
            out_path=mp4_out,
            render_profile=spec.render_profile,
        )

        hls_master_path: Optional[Path] = None
        if spec.output_format == "hls":
            if hls_dir.exists():
                shutil.rmtree(hls_dir, ignore_errors=True)
            hls_dir.mkdir(parents=True, exist_ok=True)
            master = self._packager.package_hls_abr(
                job_id=job_id,
                input_path=base_mp4,
                subtitle_ass_path=ass_path,
                out_dir=hls_dir,
                render_profile=spec.render_profile,
            )
            if master.exists():
                hls_master_path = master

        planned = self._storage.planned_urls(
            project_id=spec.project_id,
            content_hash=content_hash,
            hls_master_name=(
                hls_master_path.name if hls_master_path is not None else None
            ),
        )

        self._cache.mark_uploading(content_hash=content_hash)
        self._cache.store(
            job_id=job_id,
            content_hash=content_hash,
            mp4_path=packaged_mp4,
            hls_master_path=hls_master_path,
            mp4_url=planned.mp4_url,
            hls_master_url=planned.hls_master_url,
            upload_status="pending",
        )

        log_event(
            self._logger,
            job_id=job_id,
            step="pipeline",
            message="render_ready",
            mp4_url=planned.mp4_url,
            hls_url=planned.hls_master_url,
        )

        fut = self._storage.schedule_upload_outputs(
            job_id=job_id,
            project_id=spec.project_id,
            content_hash=content_hash,
            mp4_path=packaged_mp4,
            hls_dir=hls_dir if spec.output_format == "hls" else None,
            hls_master_path=hls_master_path,
        )

        if fut is None:
            self._cache.clear_uploading(content_hash=content_hash)
            self._cache.update_upload_result(
                job_id=job_id,
                content_hash=content_hash,
                upload_status="uploaded",
            )
        else:

            def _on_done(f):
                try:
                    r = f.result()
                    self._cache.update_upload_result(
                        job_id=job_id,
                        content_hash=content_hash,
                        upload_status="uploaded",
                        mp4_url=r.mp4_url,
                        hls_master_url=r.hls_master_url,
                    )
                except Exception as e:
                    self._cache.update_upload_result(
                        job_id=job_id,
                        content_hash=content_hash,
                        upload_status="failed",
                        upload_error=f"STORAGE_FAILED:{type(e).__name__}",
                    )
                finally:
                    self._cache.clear_uploading(content_hash=content_hash)

            fut.add_done_callback(_on_done)

        log_event(
            self._logger,
            job_id=job_id,
            step="pipeline",
            message="done",
            mp4=str(packaged_mp4),
        )
        return PipelineResult(
            cache_hit=False,
            content_hash=content_hash,
            mp4_path=packaged_mp4,
            mp4_url=planned.mp4_url,
            hls_master_path=hls_master_path,
            hls_master_url=planned.hls_master_url,
            upload_status="pending" if fut is not None else "uploaded",
        )


def _cache_payload(spec: MediaJobSpec) -> Dict[str, Any]:
    scenes = []
    for s in spec.scenes:
        scenes.append(
            {
                "clip_url": s.clip_url,
                "prompt": s.prompt,
                "expected_duration_ms": s.expected_duration_ms,
            }
        )
    subtitle_style = {
        "preset": spec.subtitle_style.preset,
        "language": spec.subtitle_style.language,
        "max_chars_per_line": spec.subtitle_style.max_chars_per_line,
        "safe_area_pct": spec.subtitle_style.safe_area_pct,
    }
    return {
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": spec.schema_version,
        "project_id": spec.project_id,
        "render_profile": spec.render_profile,
        "output_format": spec.output_format,
        "scenes": scenes,
        "voiceover_script": spec.voiceover_script,
        "subtitle_style": subtitle_style,
    }
