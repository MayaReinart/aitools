from celery import Celery
from src.core.config import settings

celery_app = Celery(
    "summarizer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.autodiscover_tasks(["tasks"])
