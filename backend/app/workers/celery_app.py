from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_call_center",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "aggregate-daily-analytics": {
        "task": "app.workers.summary_worker.aggregate_daily_analytics",
        "schedule": crontab(hour=0, minute=0),
    },
}

celery_app.autodiscover_tasks([
    "app.workers.audio_worker",
    "app.workers.call_worker",
    "app.workers.summary_worker",
])
