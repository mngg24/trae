from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import shutil
import socket
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from ..logging_utils import log_event
from .errors import ErrorDescriptor, ErrorStrategy, ErrorTaxonomy, FetcherError


@dataclass(frozen=True)
class FetcherConfig:
    timeout_sec: float = 30.0
    max_concurrency: int = 4
    max_retries: int = 3
    backoff_initial_sec: float = 0.5
    backoff_max_sec: float = 8.0
    max_content_length_bytes: int = 200 * 1024 * 1024
    cache_dir: Path = Path(".cache/videosup/fetcher")
    partial_ttl_sec: float = 24 * 60 * 60


@dataclass(frozen=True)
class FetchResult:
    url: str
    path: Path
    etag: Optional[str]
    from_cache: bool
    byte_size: int


class Fetcher:
    def __init__(
        self, *, config: FetcherConfig, logger: Optional[logging.Logger] = None
    ):
        self._cfg = config
        self._logger = logger or logging.getLogger("videosup.fetcher")
        self._cfg.cache_dir.mkdir(parents=True, exist_ok=True)
        (self._cfg.cache_dir / "blobs").mkdir(parents=True, exist_ok=True)
        self._index_path = self._cfg.cache_dir / "index.json"
        self._index = self._load_index()
        self.cleanup_partials()

    def cleanup_partials(self) -> int:
        now = time.time()
        removed = 0
        for p in (self._cfg.cache_dir / "blobs").glob("*.part"):
            try:
                if now - p.stat().st_mtime >= self._cfg.partial_ttl_sec:
                    p.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                continue
        return removed

    def fetch_many(
        self,
        *,
        job_id: str,
        urls: Iterable[str],
        step: str = "download",
    ) -> list[FetchResult]:
        url_list = list(urls)
        if not url_list:
            return []
        if self._cfg.max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")

        start = time.perf_counter()
        results: list[FetchResult] = []
        log_event(
            self._logger,
            job_id=job_id,
            step=step,
            message="fetch_many_start",
            url_count=len(url_list),
            max_concurrency=self._cfg.max_concurrency,
        )
        with ThreadPoolExecutor(max_workers=self._cfg.max_concurrency) as ex:
            futures = [
                ex.submit(self.fetch_one, job_id=job_id, url=u, step=step)
                for u in url_list
            ]
            for f in as_completed(futures):
                results.append(f.result())

        dur_ms = int((time.perf_counter() - start) * 1000)
        log_event(
            self._logger,
            job_id=job_id,
            step=step,
            duration_ms=dur_ms,
            message="fetch_many_done",
            ok_count=len(results),
        )
        return results

    def fetch_one(
        self, *, job_id: str, url: str, step: str = "download"
    ) -> FetchResult:
        start = time.perf_counter()

        cached = self._lookup_cache(url)
        headers: dict[str, str] = {}
        if cached is not None and cached.etag is not None:
            headers["If-None-Match"] = cached.etag

        attempt = 0
        last_err: Optional[Exception] = None
        while attempt <= self._cfg.max_retries:
            attempt += 1
            try:
                res = self._download(
                    job_id=job_id,
                    url=url,
                    step=step,
                    headers=headers,
                    attempt=attempt,
                    cached=cached,
                )
                dur_ms = int((time.perf_counter() - start) * 1000)
                log_event(
                    self._logger,
                    job_id=job_id,
                    step=step,
                    duration_ms=dur_ms,
                    message="fetch_one_done",
                    url=url,
                    from_cache=res.from_cache,
                    byte_size=res.byte_size,
                    attempt=attempt,
                )
                return res
            except FetcherError as e:
                last_err = e
                if e.descriptor.strategy == ErrorStrategy.ABORT:
                    raise
                if attempt > self._cfg.max_retries:
                    raise
                sleep_s = self._compute_backoff(attempt)
                log_event(
                    self._logger,
                    job_id=job_id,
                    step=step,
                    message="fetch_one_retry",
                    url=url,
                    attempt=attempt,
                    sleep_ms=int(sleep_s * 1000),
                    error_code=e.descriptor.code.value,
                )
                time.sleep(sleep_s)
            except Exception as e:
                last_err = e
                if attempt > self._cfg.max_retries:
                    raise FetcherError(
                        ErrorDescriptor(
                            code=ErrorTaxonomy.PROVIDER_TIMEOUT,
                            message="Provider error",
                            strategy=ErrorStrategy.RETRY,
                        ),
                        details=str(e),
                    ) from e
                time.sleep(self._compute_backoff(attempt))

        raise (
            last_err
            if isinstance(last_err, Exception)
            else RuntimeError("Fetcher failed unexpectedly")
        )

    def _compute_backoff(self, attempt: int) -> float:
        base = min(
            self._cfg.backoff_initial_sec * (2 ** (attempt - 1)),
            self._cfg.backoff_max_sec,
        )
        jitter = random.random() * 0.25 * base
        return base + jitter

    def _download(
        self,
        *,
        job_id: str,
        url: str,
        step: str,
        headers: dict[str, str],
        attempt: int,
        cached: Optional["_CacheEntry"],
    ) -> FetchResult:
        log_event(
            self._logger,
            job_id=job_id,
            step=step,
            message="download_start",
            url=url,
            attempt=attempt,
        )

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_sec) as resp:
                status = getattr(resp, "status", None) or resp.getcode()
                if status == 304 and cached is not None and cached.path.exists():
                    return FetchResult(
                        url=url,
                        path=cached.path,
                        etag=cached.etag,
                        from_cache=True,
                        byte_size=cached.path.stat().st_size,
                    )
                if status < 200 or status >= 300:
                    raise FetcherError(
                        ErrorDescriptor(
                            code=ErrorTaxonomy.BAD_MEDIA,
                            message="Unexpected HTTP status",
                            strategy=ErrorStrategy.ABORT,
                        ),
                        details=f"status={status}",
                    )

                content_length = resp.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        cl = int(content_length)
                    except ValueError:
                        cl = -1
                    if cl > self._cfg.max_content_length_bytes:
                        raise FetcherError(
                            ErrorDescriptor(
                                code=ErrorTaxonomy.BAD_MEDIA,
                                message="Content too large",
                                strategy=ErrorStrategy.ABORT,
                            ),
                            details=f"content_length={cl}",
                        )

                etag = resp.headers.get("ETag")
                blob_path = self._blob_path(url=url, etag=etag)
                if etag is not None:
                    existing = self._index.get(url)
                    if (
                        existing is not None
                        and existing.etag == etag
                        and existing.path.exists()
                    ):
                        return FetchResult(
                            url=url,
                            path=existing.path,
                            etag=etag,
                            from_cache=True,
                            byte_size=existing.path.stat().st_size,
                        )

                tmp_part = Path(f"{blob_path}.part")
                tmp_part.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with tmp_part.open("wb") as f:
                        shutil.copyfileobj(resp, f, length=1024 * 1024)
                    byte_size = int(tmp_part.stat().st_size)
                    os.replace(tmp_part, blob_path)
                finally:
                    tmp_part.unlink(missing_ok=True)

                self._index[url] = _CacheEntry(url=url, etag=etag, path=blob_path)
                self._save_index()

                return FetchResult(
                    url=url,
                    path=blob_path,
                    etag=etag,
                    from_cache=False,
                    byte_size=byte_size,
                )
        except urllib.error.HTTPError as e:
            if e.code == 304 and cached is not None and cached.path.exists():
                return FetchResult(
                    url=url,
                    path=cached.path,
                    etag=cached.etag,
                    from_cache=True,
                    byte_size=cached.path.stat().st_size,
                )
            if e.code == 404:
                raise FetcherError(
                    ErrorDescriptor(
                        code=ErrorTaxonomy.BAD_MEDIA,
                        message="Resource not found (404)",
                        strategy=ErrorStrategy.ABORT,
                    )
                ) from e
            if 500 <= e.code <= 599:
                raise FetcherError(
                    ErrorDescriptor(
                        code=ErrorTaxonomy.PROVIDER_TIMEOUT,
                        message="Provider server error",
                        strategy=ErrorStrategy.RETRY,
                    ),
                    details=f"status={e.code}",
                ) from e
            raise FetcherError(
                ErrorDescriptor(
                    code=ErrorTaxonomy.BAD_MEDIA,
                    message="HTTP error",
                    strategy=ErrorStrategy.ABORT,
                ),
                details=f"status={e.code}",
            ) from e
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise FetcherError(
                ErrorDescriptor(
                    code=ErrorTaxonomy.PROVIDER_TIMEOUT,
                    message="Provider timeout",
                    strategy=ErrorStrategy.RETRY,
                ),
                details=str(e),
            ) from e

    def _blob_path(self, *, url: str, etag: Optional[str]) -> Path:
        h = hashlib.sha256()
        h.update(url.encode("utf-8"))
        h.update(b"\n")
        if etag:
            h.update(etag.encode("utf-8"))
        digest = h.hexdigest()
        return self._cfg.cache_dir / "blobs" / f"{digest}.bin"

    def _load_index(self) -> dict[str, _CacheEntry]:
        if not self._index_path.exists():
            return {}
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(raw, dict):
            return {}

        out: dict[str, _CacheEntry] = {}
        for url, v in raw.items():
            if not isinstance(url, str) or not isinstance(v, dict):
                continue
            etag = v.get("etag")
            path = v.get("path")
            if path is None or not isinstance(path, str):
                continue
            if etag is not None and not isinstance(etag, str):
                continue
            out[url] = _CacheEntry(url=url, etag=etag, path=Path(path))
        return out

    def _save_index(self) -> None:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix="index.", suffix=".json", dir=str(self._cfg.cache_dir)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        u: {"etag": e.etag, "path": str(e.path)}
                        for u, e in self._index.items()
                    },
                    f,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
            os.replace(tmp_path, self._index_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _lookup_cache(self, url: str) -> Optional["_CacheEntry"]:
        e = self._index.get(url)
        if e is None:
            return None
        if not e.path.exists():
            return None
        return e


@dataclass(frozen=True)
class _CacheEntry:
    url: str
    etag: Optional[str]
    path: Path
