from celery import Celery
from src.core.config import settings

celery_app = Celery(
    "summarizer",
    broker=settings.REDIS_URL or "redis://localhost:6379/0",
    backend=settings.REDIS_URL or "redis://localhost:6379/0",
)

celery_app.autodiscover_tasks(["src.tasks"])
