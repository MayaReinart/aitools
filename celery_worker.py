from celery import Celery
from celery.app.task import Task

from src.core.config import settings

# Monkey patch Task to support Python's generic type system
Task.__class_getitem__ = classmethod(lambda cls, *_args, **_kwargs: cls)  # type: ignore[attr-defined]

celery_app = Celery(
    "summarizer",
    broker=settings.REDIS_URL or "redis://localhost:6379/0",
    backend=settings.REDIS_URL or "redis://localhost:6379/0",
)

celery_app.autodiscover_tasks(["src.tasks"])

celery_app.conf.update(
    # Use JSON for serializing task arguments (safe, readable format)
    task_serializer="json",
    # Only accept JSON-serialized messages (security measure)
    accept_content=["json"],
    # Use JSON for serializing task results
    result_serializer="json",
    # Use UTC for all datetime operations
    timezone="UTC",
    enable_utc=True,
)
