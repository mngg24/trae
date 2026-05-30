import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse


def _is_redis_reachable(redis_url: str) -> bool:
    parsed = urlparse(redis_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _posix_sqlite_db_url(db_path: Path) -> str:
    return f"sqlite+pysqlite:///{db_path.resolve().as_posix()}"


def _start_worker(*, backend_root: Path, env: dict) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "worker.celery_app",
        "worker",
        "--loglevel=WARNING",
        "--pool=solo",
        "--concurrency=1",
        "--without-heartbeat",
        "--without-gossip",
        "--without-mingle",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(backend_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _drain_output(proc: subprocess.Popen, *, max_lines: int = 200) -> str:
    if proc.stdout is None:
        return ""
    lines: list[str] = []
    for _ in range(max_lines):
        line = proc.stdout.readline()
        if not line:
            break
        lines.append(line.rstrip("\n"))
    return "\n".join(lines)


def main() -> int:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    if not _is_redis_reachable(redis_url):
        print(f"Redis not reachable at {redis_url}. Start it with: cd backend; docker compose up -d")
        return 2

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "e2e.db"
        os.environ["DB_URL"] = _posix_sqlite_db_url(db_path)
        os.environ["REDIS_URL"] = redis_url
        os.environ["CELERY_BROKER_URL"] = redis_url
        os.environ["CELERY_RESULT_BACKEND"] = redis_url

        from shared.persistence.database import engine
        from shared.persistence.models import Base

        Base.metadata.create_all(engine)

        env = dict(os.environ)
        env["PYTHONPATH"] = str(backend_root)
        worker_proc = _start_worker(backend_root=backend_root, env=env)

        try:
            time.sleep(2.0)
            if worker_proc.poll() is not None:
                output = _drain_output(worker_proc)
                print("Worker failed to start.")
                if output:
                    print(output)
                return 3

            from api.main import app
            from fastapi.testclient import TestClient

            client = TestClient(app)

            resp = client.post("/projects", json={"topic": "e2e topic", "target_duration_seconds": 60})
            if resp.status_code != 201:
                print(f"Failed to create project: status={resp.status_code} body={resp.text}")
                return 4
            project_id = resp.json()["id"]

            resp = client.post(f"/projects/{project_id}/runs", headers={"Idempotency-Key": "e2e-run"})
            if resp.status_code not in {200, 201}:
                print(f"Failed to start run: status={resp.status_code} body={resp.text}")
                return 5
            run_id = resp.json()["run"]["id"]

            deadline = time.time() + float(os.environ.get("E2E_TIMEOUT_SECONDS", "60"))
            last = None
            while time.time() < deadline:
                resp = client.get(f"/runs/{run_id}")
                if resp.status_code != 200:
                    print(f"Failed to fetch run: status={resp.status_code} body={resp.text}")
                    return 6
                run = resp.json()
                if run != last:
                    last = run
                    print(f"run={run_id} status={run['status']} current_stage={run.get('current_stage')}")
                if run["status"] in {"SUCCEEDED", "FAILED"}:
                    if run["status"] == "FAILED":
                        print(f"Pipeline failed: {run.get('error_message')}")
                        print("\n".join(run.get("log_summary") or []))
                        return 7
                    break
                time.sleep(0.5)
            else:
                print("Timed out waiting for pipeline to finish")
                return 8

            from sqlalchemy import select
            from shared.persistence import Asset, Scene, SessionLocal

            with SessionLocal() as db:
                scene_count = len(db.execute(select(Scene).where(Scene.project_id == project_id)).scalars().all())
                asset_count = len(db.execute(select(Asset).where(Asset.project_id == project_id)).scalars().all())

            print(f"Completed. scenes={scene_count} assets={asset_count}")
            if scene_count <= 0:
                return 9
            if asset_count <= 0:
                return 10
            return 0
        finally:
            worker_proc.terminate()
            try:
                worker_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker_proc.kill()
                worker_proc.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())

