from celery import Celery

from shared.config import get_settings


settings = get_settings()

celery_app = Celery(
    "worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.autodiscover_tasks(["worker"])
