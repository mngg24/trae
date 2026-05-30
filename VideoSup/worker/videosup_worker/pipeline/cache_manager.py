from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..logging_utils import log_event


@dataclass(frozen=True)
class CacheResult:
    hit: bool
    content_hash: str
    mp4_path: Optional[Path] = None
    mp4_url: Optional[str] = None
    hls_master_path: Optional[Path] = None
    hls_master_url: Optional[str] = None


class CacheManager:
    def __init__(self, *, cache_dir: Path, logger: Optional[logging.Logger] = None):
        self._cache_dir = cache_dir
        self._logger = logger or logging.getLogger("videosup.cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        (self._cache_dir / "mp4").mkdir(parents=True, exist_ok=True)
        (self._cache_dir / "hls").mkdir(parents=True, exist_ok=True)
        (self._cache_dir / "uploading").mkdir(parents=True, exist_ok=True)
        self._index_path = self._cache_dir / "index.json"
        self._lock = threading.Lock()
        self._index = self._load_index()

    def compute_hash(self, payload: Dict[str, Any]) -> str:
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def cache_lookup(self, *, job_id: str, payload: Dict[str, Any]) -> CacheResult:
        h = self.compute_hash(payload)
        with self._lock:
            entry = self._index.get(h)
        if not isinstance(entry, dict):
            return CacheResult(hit=False, content_hash=h)
        mp4 = entry.get("mp4_path")
        mp4_url = entry.get("mp4_url")
        hls = entry.get("hls_master_path")
        hls_url = entry.get("hls_master_url")
        mp4_path = Path(mp4) if isinstance(mp4, str) else None
        hls_path = Path(hls) if isinstance(hls, str) else None
        if (
            mp4_path is not None
            and not mp4_path.exists()
            and not isinstance(mp4_url, str)
        ):
            return CacheResult(hit=False, content_hash=h)
        if hls_path is not None and not hls_path.exists():
            hls_path = None
        log_event(
            self._logger,
            job_id=job_id,
            step="cache",
            message="cache_hit",
            content_hash=h,
        )
        return CacheResult(
            hit=True,
            content_hash=h,
            mp4_path=mp4_path,
            mp4_url=mp4_url if isinstance(mp4_url, str) else None,
            hls_master_path=hls_path,
            hls_master_url=hls_url if isinstance(hls_url, str) else None,
        )

    def cache_paths(self, *, content_hash: str) -> Dict[str, Path]:
        return {
            "mp4": self._cache_dir / "mp4" / f"{content_hash}.mp4",
            "hls_dir": self._cache_dir / "hls" / content_hash,
            "hls_master": self._cache_dir / "hls" / content_hash / "master.m3u8",
        }

    def store(
        self,
        *,
        job_id: str,
        content_hash: str,
        mp4_path: Path,
        hls_master_path: Optional[Path],
        mp4_url: Optional[str] = None,
        hls_master_url: Optional[str] = None,
        upload_status: str = "pending",
        upload_error: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._index[content_hash] = {
                "mp4_path": str(mp4_path),
                "hls_master_path": (
                    str(hls_master_path) if hls_master_path is not None else None
                ),
                "mp4_url": mp4_url,
                "hls_master_url": hls_master_url,
                "upload_status": upload_status,
                "upload_error": upload_error,
                "updated_at": int(time.time()),
            }
            self._save_index_locked()
        log_event(
            self._logger,
            job_id=job_id,
            step="cache",
            message="cache_store",
            content_hash=content_hash,
        )

    def update_upload_result(
        self,
        *,
        job_id: str,
        content_hash: str,
        upload_status: str,
        upload_error: Optional[str] = None,
        mp4_url: Optional[str] = None,
        hls_master_url: Optional[str] = None,
    ) -> None:
        with self._lock:
            entry = self._index.get(content_hash)
            if not isinstance(entry, dict):
                entry = {}
                self._index[content_hash] = entry
            entry["upload_status"] = upload_status
            entry["upload_error"] = upload_error
            entry["updated_at"] = int(time.time())
            if mp4_url is not None:
                entry["mp4_url"] = mp4_url
            if hls_master_url is not None:
                entry["hls_master_url"] = hls_master_url
            self._save_index_locked()
        log_event(
            self._logger,
            job_id=job_id,
            step="cache",
            message="upload_update",
            content_hash=content_hash,
            upload_status=upload_status,
        )

    def upload_marker_path(self, *, content_hash: str) -> Path:
        return self._cache_dir / "uploading" / f"{content_hash}.lock"

    def mark_uploading(self, *, content_hash: str) -> None:
        p = self.upload_marker_path(content_hash=content_hash)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("uploading\n", encoding="utf-8")

    def clear_uploading(self, *, content_hash: str) -> None:
        p = self.upload_marker_path(content_hash=content_hash)
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass

    def _load_index(self) -> Dict[str, Any]:
        if not self._index_path.exists():
            return {}
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _save_index(self) -> None:
        with self._lock:
            self._save_index_locked()

    def _save_index_locked(self) -> None:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix="index.", suffix=".json", dir=str(self._cache_dir)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, sort_keys=True, indent=2)
            os.replace(tmp_path, self._index_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
