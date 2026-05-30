import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    db_url: str
    cors_allow_origins: tuple[str, ...]
    videosup_base_url: str
    videosup_poll_interval_sec: float
    videosup_max_poll_sec: float


def get_settings() -> Settings:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url = os.getenv("CELERY_BROKER_URL", redis_url)
    celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", redis_url)

    default_db_path = (Path(__file__).resolve().parents[1] / "app.db").as_posix()
    db_url = os.getenv("DB_URL", f"sqlite+pysqlite:///{default_db_path}")

    cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173")
    cors_allow_origins = tuple(o.strip() for o in cors_raw.split(",") if o.strip())

    videosup_base_url = os.getenv("VIDEOSUP_BASE_URL", "http://localhost:9010").rstrip("/")
    videosup_poll_interval_sec = float(os.getenv("VIDEOSUP_POLL_INTERVAL_SEC", "2"))
    videosup_max_poll_sec = float(os.getenv("VIDEOSUP_MAX_POLL_SEC", "600"))
    return Settings(
        redis_url=redis_url,
        celery_broker_url=celery_broker_url,
        celery_result_backend=celery_result_backend,
        db_url=db_url,
        cors_allow_origins=cors_allow_origins,
        videosup_base_url=videosup_base_url,
        videosup_poll_interval_sec=videosup_poll_interval_sec,
        videosup_max_poll_sec=videosup_max_poll_sec,
    )
