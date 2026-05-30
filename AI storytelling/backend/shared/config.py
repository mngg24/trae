import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    db_url: str


def get_settings() -> Settings:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url = os.getenv("CELERY_BROKER_URL", redis_url)
    celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", redis_url)

    default_db_path = (Path(__file__).resolve().parents[1] / "app.db").as_posix()
    db_url = os.getenv("DB_URL", f"sqlite+pysqlite:///{default_db_path}")
    return Settings(
        redis_url=redis_url,
        celery_broker_url=celery_broker_url,
        celery_result_backend=celery_result_backend,
        db_url=db_url,
    )
