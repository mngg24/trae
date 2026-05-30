from __future__ import annotations

import concurrent.futures
import logging
import mimetypes
import os
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from .logging_utils import log_event


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StorageConfig:
    backend: str
    local_dir: Path
    s3_endpoint_url: Optional[str]
    s3_region: Optional[str]
    s3_bucket: Optional[str]
    s3_prefix: str
    s3_public_base_url: Optional[str]
    s3_public_url_template: Optional[str]
    max_concurrency: int
    upload_mode: str
    upload_delay_ms: int
    bg_max_workers: int


@dataclass(frozen=True)
class UploadResult:
    mp4_url: str
    hls_master_url: Optional[str] = None


class StorageManager:
    _bg_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
    _bg_lock = threading.Lock()

    def __init__(
        self, *, config: StorageConfig, logger: Optional[logging.Logger] = None
    ):
        self._cfg = config
        self._logger = logger or logging.getLogger("videosup.storage")
        if self._cfg.backend == "local":
            self._cfg.local_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def from_env(*, logger: Optional[logging.Logger] = None) -> "StorageManager":
        backend = os.environ.get("VIDEOSUP_STORAGE_BACKEND", "local").strip().lower()
        local_dir = Path(
            os.environ.get("VIDEOSUP_STORAGE_LOCAL_DIR", ".storage/videosup")
        ).resolve()

        s3_endpoint_url = os.environ.get("VIDEOSUP_S3_ENDPOINT_URL")
        s3_region = os.environ.get("VIDEOSUP_S3_REGION")
        s3_bucket = os.environ.get("VIDEOSUP_S3_BUCKET")
        s3_prefix = os.environ.get("VIDEOSUP_S3_PREFIX", "videosup").strip("/")
        s3_public_base_url = os.environ.get("VIDEOSUP_S3_PUBLIC_BASE_URL")
        s3_public_url_template = os.environ.get("VIDEOSUP_S3_PUBLIC_URL_TEMPLATE")
        max_concurrency = int(os.environ.get("VIDEOSUP_STORAGE_MAX_CONCURRENCY", "8"))
        upload_mode = os.environ.get("VIDEOSUP_UPLOAD_MODE", "async").strip().lower()
        upload_delay_ms = int(os.environ.get("VIDEOSUP_STORAGE_UPLOAD_DELAY_MS", "0"))
        bg_max_workers = int(os.environ.get("VIDEOSUP_UPLOAD_MAX_WORKERS", "2"))

        cfg = StorageConfig(
            backend=backend,
            local_dir=local_dir,
            s3_endpoint_url=s3_endpoint_url,
            s3_region=s3_region,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            s3_public_base_url=s3_public_base_url,
            s3_public_url_template=s3_public_url_template,
            max_concurrency=max_concurrency,
            upload_mode=upload_mode,
            upload_delay_ms=upload_delay_ms,
            bg_max_workers=bg_max_workers,
        )
        return StorageManager(config=cfg, logger=logger)

    def planned_urls(
        self, *, project_id: str, content_hash: str, hls_master_name: Optional[str]
    ) -> UploadResult:
        key_prefix = f"{self._cfg.s3_prefix}/{project_id}/{content_hash}"
        mp4_key = f"{key_prefix}/video.mp4"
        if self._cfg.backend == "local":
            mp4_dst = (self._cfg.local_dir / mp4_key).resolve()
            mp4_url = f"file:///{mp4_dst.as_posix()}"
            hls_url = None
            if hls_master_name:
                hls_dst = (
                    self._cfg.local_dir / f"{key_prefix}/hls/{hls_master_name}"
                ).resolve()
                hls_url = f"file:///{hls_dst.as_posix()}"
            return UploadResult(mp4_url=mp4_url, hls_master_url=hls_url)

        hls_url = None
        if hls_master_name:
            hls_url = self._public_url(f"{key_prefix}/hls/{hls_master_name}")
        return UploadResult(mp4_url=self._public_url(mp4_key), hls_master_url=hls_url)

    def schedule_upload_outputs(
        self,
        *,
        job_id: str,
        project_id: str,
        content_hash: str,
        mp4_path: Path,
        hls_dir: Optional[Path],
        hls_master_path: Optional[Path],
    ) -> Optional[concurrent.futures.Future]:
        if self._cfg.upload_mode != "async":
            self.upload_outputs(
                job_id=job_id,
                project_id=project_id,
                content_hash=content_hash,
                mp4_path=mp4_path,
                hls_dir=hls_dir,
                hls_master_path=hls_master_path,
            )
            return None

        with StorageManager._bg_lock:
            if StorageManager._bg_executor is None:
                StorageManager._bg_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self._cfg.bg_max_workers
                )

        def _task() -> UploadResult:
            if self._cfg.upload_delay_ms > 0:
                time.sleep(self._cfg.upload_delay_ms / 1000.0)
            return self.upload_outputs(
                job_id=job_id,
                project_id=project_id,
                content_hash=content_hash,
                mp4_path=mp4_path,
                hls_dir=hls_dir,
                hls_master_path=hls_master_path,
            )

        assert StorageManager._bg_executor is not None
        log_event(self._logger, job_id=job_id, step="upload", message="upload_enqueued")
        return StorageManager._bg_executor.submit(_task)

    def upload_outputs(
        self,
        *,
        job_id: str,
        project_id: str,
        content_hash: str,
        mp4_path: Path,
        hls_dir: Optional[Path],
        hls_master_path: Optional[Path],
    ) -> UploadResult:
        key_prefix = f"{self._cfg.s3_prefix}/{project_id}/{content_hash}"

        mp4_key = f"{key_prefix}/video.mp4"
        mp4_url = self._upload_file(
            job_id=job_id,
            path=mp4_path,
            key=mp4_key,
            cache_control=_cache_control_for_suffix(".mp4"),
        )

        hls_url = None
        if (
            hls_dir is not None
            and hls_master_path is not None
            and hls_master_path.exists()
        ):
            hls_prefix = f"{key_prefix}/hls"
            self._upload_dir(job_id=job_id, root=hls_dir, key_prefix=hls_prefix)
            master_key = f"{hls_prefix}/{hls_master_path.name}"
            hls_url = self._public_url(master_key)

        return UploadResult(mp4_url=mp4_url, hls_master_url=hls_url)

    def _upload_dir(self, *, job_id: str, root: Path, key_prefix: str) -> None:
        files: list[Tuple[Path, str]] = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            files.append((p, f"{key_prefix}/{rel}"))

        start = time.perf_counter()
        log_event(
            self._logger,
            job_id=job_id,
            step="upload",
            message="dir_upload_start",
            file_count=len(files),
        )

        if self._cfg.max_concurrency <= 1 or len(files) <= 1:
            for p, key in files:
                self._upload_file(
                    job_id=job_id,
                    path=p,
                    key=key,
                    cache_control=_cache_control_for_suffix(p.suffix),
                )
        else:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self._cfg.max_concurrency
            ) as ex:
                futures = []
                for p, key in files:
                    futures.append(
                        ex.submit(
                            self._upload_file,
                            job_id=job_id,
                            path=p,
                            key=key,
                            cache_control=_cache_control_for_suffix(p.suffix),
                        )
                    )
                for f in concurrent.futures.as_completed(futures):
                    f.result()

        dur_ms = int((time.perf_counter() - start) * 1000)
        log_event(
            self._logger,
            job_id=job_id,
            step="upload",
            duration_ms=dur_ms,
            message="dir_upload_done",
        )

    def _upload_file(
        self, *, job_id: str, path: Path, key: str, cache_control: str
    ) -> str:
        if self._cfg.backend == "local":
            dst = (self._cfg.local_dir / key).resolve()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
            url = f"file:///{dst.as_posix()}"
            log_event(
                self._logger,
                job_id=job_id,
                step="upload",
                message="file_uploaded",
                key=key,
                url=url,
            )
            return url

        if self._cfg.backend != "s3":
            raise StorageError(f"Unsupported storage backend: {self._cfg.backend}")

        client, bucket = _s3_client_and_bucket(self._cfg)
        _ensure_bucket(client=client, bucket=bucket)

        content_type = _guess_content_type(path)
        extra_args: Dict[str, str] = {"CacheControl": cache_control}
        if content_type is not None:
            extra_args["ContentType"] = content_type

        client.upload_file(
            Filename=str(path),
            Bucket=bucket,
            Key=key,
            ExtraArgs=extra_args,
        )
        url = self._public_url(key)
        log_event(
            self._logger,
            job_id=job_id,
            step="upload",
            message="file_uploaded",
            key=key,
            url=url,
        )
        return url

    def _public_url(self, key: str) -> str:
        bucket = self._cfg.s3_bucket or "unknown"
        if self._cfg.s3_public_url_template:
            return self._cfg.s3_public_url_template.format(bucket=bucket, key=key)
        base = self._cfg.s3_public_base_url or self._cfg.s3_endpoint_url
        if base:
            base = base.rstrip("/")
            return f"{base}/{bucket}/{key}"
        return f"s3://{bucket}/{key}"


def _guess_content_type(p: Path) -> Optional[str]:
    if p.suffix.lower() == ".m3u8":
        return "application/vnd.apple.mpegurl"
    if p.suffix.lower() == ".ts":
        return "video/mp2t"
    if p.suffix.lower() == ".mp4":
        return "video/mp4"
    if p.suffix.lower() == ".ass":
        return "text/x-ssa"
    ct, _ = mimetypes.guess_type(str(p))
    return ct


def _cache_control_for_suffix(suffix: str) -> str:
    s = suffix.lower()
    if s == ".ts":
        return "public, max-age=31536000, immutable"
    if s == ".m3u8":
        return "no-cache, max-age=0"
    if s == ".mp4":
        return "public, max-age=31536000, immutable"
    return "public, max-age=86400"


def _s3_client_and_bucket(cfg: StorageConfig):
    try:
        import boto3
        from botocore.config import Config
    except Exception as e:
        raise StorageError("boto3 is required for S3 backend") from e

    access = os.environ.get("VIDEOSUP_S3_ACCESS_KEY_ID")
    secret = os.environ.get("VIDEOSUP_S3_SECRET_ACCESS_KEY")
    if not cfg.s3_bucket:
        raise StorageError("VIDEOSUP_S3_BUCKET is required for S3 backend")

    session = boto3.session.Session(
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=cfg.s3_region,
    )
    client = session.client(
        "s3",
        endpoint_url=cfg.s3_endpoint_url,
        config=Config(s3={"addressing_style": "path"}),
    )
    return client, cfg.s3_bucket


def _ensure_bucket(*, client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)
