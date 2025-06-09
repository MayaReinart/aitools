"""Celery application configuration."""

from celery import Celery
from loguru import logger

from src.core.config import settings

# Initialize Celery app
logger.info(f"Initializing Celery app with Redis URL: {settings.REDIS_URL}")
celery_app = Celery(
    "api_introspection",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Time settings
    timezone="UTC",
    enable_utc=True,
    # Task tracking settings
    task_track_started=True,
    task_track_received=True,
    task_send_sent_event=True,
    # Worker settings
    worker_redirect_stdouts=False,  # Don't redirect stdout/stderr
    worker_redirect_stdouts_level="INFO",
    # Task discovery settings
    imports=("src.tasks.pipeline",),  # Explicitly import tasks module
    task_default_queue="api_introspection",  # Default queue for tasks
    task_default_exchange="api_introspection",  # Default exchange for tasks
    task_default_routing_key="api_introspection",  # Default routing key
)

# Import tasks module to ensure tasks are registered
import src.tasks.pipeline  # noqa
