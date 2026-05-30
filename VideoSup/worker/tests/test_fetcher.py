import io
import os
import socket
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from typing import Dict, Optional

from videosup_worker.fetcher import (
    ErrorStrategy,
    ErrorTaxonomy,
    Fetcher,
    FetcherConfig,
    FetcherError,
)


class _DummyResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        headers: Optional[Dict[str, str]] = None
    ):
        self._bio = io.BytesIO(body)
        self.status = status
        self.headers = headers or {}

    def getcode(self) -> int:
        return self.status

    def read(self, n: int = -1) -> bytes:
        return self._bio.read(n)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FetcherTests(unittest.TestCase):
    def test_download_success(self):
        body = b"hello-world"
        etag = '"abc"'
        with tempfile.TemporaryDirectory() as td:
            cfg = FetcherConfig(
                cache_dir=Path(td), max_retries=0, max_concurrency=1, timeout_sec=1
            )
            f = Fetcher(config=cfg)

            def _urlopen(req, timeout):
                self.assertEqual(timeout, 1)
                return _DummyResponse(
                    body,
                    status=200,
                    headers={"ETag": etag, "Content-Length": str(len(body))},
                )

            with patch("urllib.request.urlopen", side_effect=_urlopen):
                res = f.fetch_one(
                    job_id="job1", url="https://example.invalid/clip1.mp4"
                )

            self.assertTrue(res.path.exists())
            self.assertEqual(res.etag, etag)
            self.assertFalse(res.from_cache)
            self.assertEqual(res.byte_size, len(body))
            self.assertEqual(res.path.read_bytes(), body)

    def test_download_404_abort(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = FetcherConfig(
                cache_dir=Path(td), max_retries=3, max_concurrency=1, timeout_sec=1
            )
            f = Fetcher(config=cfg)

            def _urlopen(req, timeout):
                raise urllib.error.HTTPError(
                    req.full_url, 404, "Not Found", hdrs=None, fp=None
                )

            with patch("urllib.request.urlopen", side_effect=_urlopen):
                with self.assertRaises(FetcherError) as ctx:
                    f.fetch_one(
                        job_id="job1", url="https://example.invalid/missing.mp4"
                    )

            self.assertEqual(ctx.exception.descriptor.code, ErrorTaxonomy.BAD_MEDIA)
            self.assertEqual(ctx.exception.descriptor.strategy, ErrorStrategy.ABORT)

    def test_timeout_retry_then_success(self):
        body = b"ok"
        calls = {"n": 0}
        with tempfile.TemporaryDirectory() as td:
            cfg = FetcherConfig(
                cache_dir=Path(td), max_retries=2, max_concurrency=1, timeout_sec=1
            )
            f = Fetcher(config=cfg)

            def _urlopen(req, timeout):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise socket.timeout("timed out")
                return _DummyResponse(
                    body, status=200, headers={"Content-Length": str(len(body))}
                )

            with patch("urllib.request.urlopen", side_effect=_urlopen):
                res = f.fetch_one(job_id="job1", url="https://example.invalid/slow.mp4")

            self.assertEqual(calls["n"], 2)
            self.assertTrue(res.path.exists())
            self.assertEqual(res.path.read_bytes(), body)

    def test_timeout_retry_exhausted(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = FetcherConfig(
                cache_dir=Path(td),
                max_retries=1,
                max_concurrency=1,
                timeout_sec=1,
                backoff_initial_sec=0,
            )
            f = Fetcher(config=cfg)

            def _urlopen(req, timeout):
                raise socket.timeout("timed out")

            with patch("urllib.request.urlopen", side_effect=_urlopen):
                with self.assertRaises(FetcherError) as ctx:
                    f.fetch_one(
                        job_id="job1", url="https://example.invalid/always-timeout.mp4"
                    )

            self.assertEqual(
                ctx.exception.descriptor.code, ErrorTaxonomy.PROVIDER_TIMEOUT
            )
            self.assertEqual(ctx.exception.descriptor.strategy, ErrorStrategy.RETRY)

    def test_cleanup_partials(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = FetcherConfig(
                cache_dir=Path(td),
                max_retries=0,
                max_concurrency=1,
                timeout_sec=1,
                partial_ttl_sec=0,
            )
            f = Fetcher(config=cfg)

            blob_dir = Path(td) / "blobs"
            blob_dir.mkdir(parents=True, exist_ok=True)
            p = blob_dir / "orphan.part"
            p.write_bytes(b"x")
            os.utime(p, (time.time() - 1000, time.time() - 1000))

            removed = f.cleanup_partials()
            self.assertGreaterEqual(removed, 1)
            self.assertFalse(p.exists())


if __name__ == "__main__":
    unittest.main()
