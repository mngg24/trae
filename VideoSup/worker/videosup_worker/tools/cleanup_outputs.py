from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path


def main() -> int:
    cache_dir = Path(
        os.environ.get("VIDEOSUP_RENDER_CACHE_DIR", ".cache/videosup/render")
    ).resolve()
    ttl_days = int(os.environ.get("VIDEOSUP_RENDER_CACHE_TTL_DAYS", "7"))
    cutoff = time.time() - ttl_days * 24 * 60 * 60

    mp4_dir = cache_dir / "mp4"
    hls_dir = cache_dir / "hls"
    uploading_dir = cache_dir / "uploading"
    removed = 0

    for p in mp4_dir.glob("*.mp4"):
        try:
            content_hash = p.stem
            if (uploading_dir / f"{content_hash}.lock").exists():
                continue
            if p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue

    for d in hls_dir.glob("*"):
        try:
            if (uploading_dir / f"{d.name}.lock").exists():
                continue
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except OSError:
            continue

    sys.stdout.write(
        f"cleanup_outputs removed={removed} cache_dir={cache_dir} ttl_days={ttl_days}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
