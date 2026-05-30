from __future__ import annotations

import os
import sys
import time
import urllib.request


def main() -> int:
    url = os.environ.get("VIDEOSUP_WAIT_URL", "http://minio:9000/minio/health/ready")
    timeout_sec = float(os.environ.get("VIDEOSUP_WAIT_TIMEOUT_SEC", "60"))
    interval_sec = float(os.environ.get("VIDEOSUP_WAIT_INTERVAL_SEC", "1"))

    deadline = time.time() + timeout_sec
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.getcode() == 200:
                    sys.stdout.write(f"wait_for_http ok url={url}\n")
                    return 0
        except Exception as e:
            last_err = e
        time.sleep(interval_sec)

    sys.stderr.write(f"wait_for_http timeout url={url} err={last_err}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
