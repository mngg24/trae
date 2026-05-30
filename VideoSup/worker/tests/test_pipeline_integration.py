import shutil
import tempfile
import unittest
import os
import contextlib
import json
import time
from pathlib import Path

from videosup_worker.contracts import validate_media_job_spec
from videosup_worker.pipeline import Pipeline, PipelineConfig
from videosup_worker.pipeline.ffmpeg import ffprobe_media


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(_has_ffmpeg(), "ffmpeg/ffprobe not found in PATH")
class PipelineIntegrationTests(unittest.TestCase):
    def test_pipeline_mp4_and_hls_and_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with _env_context(
                {
                    "VIDEOSUP_STORAGE_BACKEND": os.environ.get(
                        "VIDEOSUP_STORAGE_BACKEND", "local"
                    ),
                    "VIDEOSUP_STORAGE_LOCAL_DIR": str(root / "storage"),
                    "VIDEOSUP_UPLOAD_MODE": "async",
                    "VIDEOSUP_STORAGE_UPLOAD_DELAY_MS": "500",
                }
            ):
                assets = root / "assets"
                assets.mkdir(parents=True, exist_ok=True)
                clip1 = assets / "clip1_640x360_25fps.mp4"
                clip2 = assets / "clip2_1280x720_30fps.mp4"
                voice = assets / "voice.wav"
                _ensure_assets(clip1=clip1, clip2=clip2, voice=voice)

                cfg = PipelineConfig(work_dir=root / "work", cache_dir=root / "cache")
                p = Pipeline(config=cfg)

                spec_dict = {
                    "schema_version": "1.0.0",
                    "job_id": "job_it_1",
                    "project_id": "proj",
                    "created_at": "2026-05-30T10:00:00Z",
                    "render_profile": "final",
                    "output_format": "hls",
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "clip_url": "https://example.invalid/c1",
                            "prompt": "a",
                            "expected_duration_ms": 1000,
                        },
                        {
                            "scene_id": "s2",
                            "clip_url": "https://example.invalid/c2",
                            "prompt": "b",
                            "expected_duration_ms": 1000,
                        },
                    ],
                    "voiceover_script": "Xin chào thế giới",
                    "subtitle_style": {
                        "preset": "tiktok_bounce",
                        "language": "vi",
                        "max_chars_per_line": 24,
                        "safe_area_pct": 0.12,
                    },
                    "state": {"status": "queued"},
                }
                spec = validate_media_job_spec(spec_dict)

                res1 = p.run(
                    job_id=spec.job_id,
                    spec=spec,
                    clip_paths=[clip1, clip2],
                    voiceover_audio_path=voice,
                )
                self.assertFalse(res1.cache_hit)
                self.assertIsNotNone(res1.mp4_url)
                self.assertTrue(res1.mp4_path is not None and res1.mp4_path.exists())
                self.assertIsNotNone(res1.hls_master_path)
                self.assertTrue(res1.hls_master_path.exists())
                self.assertIsNotNone(res1.hls_master_url)
                self.assertEqual(res1.upload_status, "pending")

                info = ffprobe_media(job_id=spec.job_id, step="verify", logger=p._logger, path=res1.mp4_path)  # type: ignore[arg-type,attr-defined]
                self.assertTrue(info.has_video)

                voice_info = ffprobe_media(job_id=spec.job_id, step="verify_voice", logger=p._logger, path=voice)  # type: ignore[attr-defined]
                self.assertIsNotNone(voice_info.duration_sec)
                self.assertLess(abs(info.duration_sec - voice_info.duration_sec), 0.6)

                idx = json.loads(
                    (cfg.cache_dir / "index.json").read_text(encoding="utf-8")
                )
                entry = idx.get(res1.content_hash, {})
                deadline = time.time() + 10
                while time.time() < deadline:
                    idx = json.loads(
                        (cfg.cache_dir / "index.json").read_text(encoding="utf-8")
                    )
                    entry = idx.get(res1.content_hash, {})
                    if entry.get("upload_status") in ("uploaded", "failed"):
                        break
                    time.sleep(0.2)
                self.assertEqual(entry.get("upload_status"), "uploaded")

                res2 = p.run(
                    job_id=spec.job_id,
                    spec=spec,
                    clip_paths=[clip1, clip2],
                    voiceover_audio_path=voice,
                )
                self.assertTrue(res2.cache_hit)
                self.assertEqual(res1.mp4_path, res2.mp4_path)
                self.assertEqual(res1.mp4_url, res2.mp4_url)

    def test_no_temp_leak_after_multiple_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with _env_context(
                {
                    "VIDEOSUP_STORAGE_BACKEND": os.environ.get(
                        "VIDEOSUP_STORAGE_BACKEND", "local"
                    ),
                    "VIDEOSUP_STORAGE_LOCAL_DIR": str(root / "storage"),
                }
            ):
                assets = root / "assets"
                assets.mkdir(parents=True, exist_ok=True)
                clip1 = assets / "clip1_640x360_25fps.mp4"
                clip2 = assets / "clip2_1280x720_30fps.mp4"
                voice = assets / "voice.wav"
                _ensure_assets(clip1=clip1, clip2=clip2, voice=voice)

                cfg = PipelineConfig(work_dir=root / "work", cache_dir=root / "cache")
                p = Pipeline(config=cfg)

                for i in range(10):
                    spec_dict = {
                        "schema_version": "1.0.0",
                        "job_id": f"job_it_{i}",
                        "project_id": "proj",
                        "created_at": "2026-05-30T10:00:00Z",
                        "render_profile": "preview" if i % 2 == 0 else "final",
                        "output_format": "mp4",
                        "scenes": [
                            {
                                "scene_id": "s1",
                                "clip_url": f"https://example.invalid/c1?i={i}",
                                "prompt": f"a{i}",
                                "expected_duration_ms": 1000,
                            },
                            {
                                "scene_id": "s2",
                                "clip_url": f"https://example.invalid/c2?i={i}",
                                "prompt": f"b{i}",
                                "expected_duration_ms": 1000,
                            },
                        ],
                        "voiceover_script": f"Xin chào {i}",
                        "subtitle_style": {
                            "preset": "tiktok_bounce",
                            "language": "vi",
                            "max_chars_per_line": 24,
                            "safe_area_pct": 0.12,
                        },
                        "state": {"status": "queued"},
                    }
                    spec = validate_media_job_spec(spec_dict)

                    try:
                        if i % 3 == 0:
                            p.run(
                                job_id=spec.job_id,
                                spec=spec,
                                clip_paths=[Path("missing.mp4"), clip2],
                                voiceover_audio_path=voice,
                            )
                        else:
                            r = p.run(
                                job_id=spec.job_id,
                                spec=spec,
                                clip_paths=[clip1, clip2],
                                voiceover_audio_path=voice,
                            )
                            self.assertIsNotNone(r.mp4_url)
                            self.assertTrue(
                                r.mp4_path is not None and r.mp4_path.exists()
                            )
                    except Exception:
                        pass

                    work_dir = cfg.work_dir
                    leftovers = list(work_dir.glob("*"))
                    self.assertEqual(
                        leftovers, [], f"Work dir leak detected: {leftovers}"
                    )

    def test_path_with_spaces_and_special_chars(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "tmp space #1"
            root.mkdir(parents=True, exist_ok=True)
            with _env_context(
                {
                    "VIDEOSUP_STORAGE_BACKEND": os.environ.get(
                        "VIDEOSUP_STORAGE_BACKEND", "local"
                    ),
                    "VIDEOSUP_STORAGE_LOCAL_DIR": str(root / "storage out"),
                }
            ):
                assets = root / "assets"
                assets.mkdir(parents=True, exist_ok=True)
                clip1 = assets / "clip1_640x360_25fps.mp4"
                clip2 = assets / "clip2_1280x720_30fps.mp4"
                voice = assets / "voice.wav"
                _ensure_assets(clip1=clip1, clip2=clip2, voice=voice)

                cfg = PipelineConfig(
                    work_dir=root / "work dir", cache_dir=root / "cache dir"
                )
                p = Pipeline(config=cfg)

                spec_dict = {
                    "schema_version": "1.0.0",
                    "job_id": "job_space_1",
                    "project_id": "proj",
                    "created_at": "2026-05-30T10:00:00Z",
                    "render_profile": "final",
                    "output_format": "mp4",
                    "scenes": [
                        {
                            "scene_id": "s1",
                            "clip_url": "https://example.invalid/c1",
                            "prompt": "a",
                            "expected_duration_ms": 1000,
                        },
                        {
                            "scene_id": "s2",
                            "clip_url": "https://example.invalid/c2",
                            "prompt": "b",
                            "expected_duration_ms": 1000,
                        },
                    ],
                    "voiceover_script": "Xin chào",
                    "subtitle_style": {
                        "preset": "tiktok_bounce",
                        "language": "vi",
                        "max_chars_per_line": 24,
                        "safe_area_pct": 0.12,
                    },
                    "state": {"status": "queued"},
                }
                spec = validate_media_job_spec(spec_dict)
                r = p.run(
                    job_id=spec.job_id,
                    spec=spec,
                    clip_paths=[clip1, clip2],
                    voiceover_audio_path=voice,
                )
                self.assertIsNotNone(r.mp4_url)
                self.assertTrue(r.mp4_path is not None and r.mp4_path.exists())


@contextlib.contextmanager
def _env_context(values):
    old = dict(os.environ)
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        os.environ.clear()
        os.environ.update(old)


def _ensure_assets(*, clip1: Path, clip2: Path, voice: Path) -> None:
    if clip1.exists() and clip2.exists() and voice.exists():
        return
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not available for assets")

    clip1.parent.mkdir(parents=True, exist_ok=True)

    if not clip1.exists():
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=640x360:d=1:r=25",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-shortest",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                str(clip1),
            ]
        )
    if not clip2.exists():
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=1280x720:d=1:r=30",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-shortest",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                str(clip2),
            ]
        )
    if not voice.exists():
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2.6",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "48000",
                "-ac",
                "1",
                str(voice),
            ]
        )


def _run(argv):
    import subprocess

    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
