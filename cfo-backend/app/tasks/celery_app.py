from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cfo",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.autodiscover_tasks([
    "app.tasks.receipt_processing",
    "app.tasks.ai_extraction",
    "app.tasks.duplicate_detection",
    "app.tasks.telegram_responses",
    "app.tasks.journal_posting",
    "app.tasks.report_generation",
    "app.tasks.notifications",
])

celery_app.conf.task_routes = {
    "app.tasks.receipt_processing.*": {"queue": "receipt-processing"},
    "app.tasks.ai_extraction.*": {"queue": "ai-extraction"},
    "app.tasks.duplicate_detection.*": {"queue": "duplicate-detection"},
    "app.tasks.telegram_responses.*": {"queue": "telegram-responses"},
    "app.tasks.journal_posting.*": {"queue": "journal-posting"},
    "app.tasks.report_generation.*": {"queue": "report-generation"},
    "app.tasks.notifications.*": {"queue": "notifications"},
}

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
