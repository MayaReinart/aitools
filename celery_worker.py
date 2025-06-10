"""Celery worker configuration."""

from types import TracebackType
from typing import Any, cast

from celery import Task
from celery.signals import (
    task_failure,
    task_prerun,
    task_received,
    task_revoked,
    task_success,
    worker_init,
    worker_ready,
)
from celery.worker.request import Request
from loguru import Logger

from src.core.celery_app import celery_app
from src.core.logging import get_logger, setup_logging

logger = cast(Logger, get_logger())

# Import tasks to register them
# Even though it appears unused, this import is necessary
import src.tasks.pipeline  # noqa

# Export the Celery app instance
celery = celery_app


# Celery signal handlers
@worker_init.connect
def init_worker(**_kwargs: dict[str, Any]) -> None:
    """Log when worker initializes."""
    logger.info("Initializing Celery worker")


@worker_ready.connect
def worker_ready_handler(**_kwargs: dict[str, Any]) -> None:
    """Log when worker is ready."""
    logger.info("Celery worker is ready")


@task_received.connect
def task_received_handler(
    request: Request | None = None, **_kwargs: dict[str, Any]
) -> None:
    """Log when task is received."""
    if request:
        logger.info(f"Task received: {request.task}[{request.id}]")


@task_prerun.connect
def task_prerun_handler(
    task_id: str | None = None,
    task: Task | None = None,
    **_kwargs: dict[str, Any],
) -> None:
    """Log before task execution."""
    if task_id and task:
        logger.info(f"Starting task: {task.name}[{task_id}]")


@task_success.connect
def task_success_handler(sender: Task | None = None, **_kwargs: dict[str, Any]) -> None:
    """Log successful task completion."""
    if sender and sender.request and sender.request.id:
        logger.info(f"Task completed successfully: {sender.name}[{sender.request.id}]")


@task_failure.connect
def task_failure_handler(
    task_id: str | None = None,
    exception: Exception | None = None,
    traceback: TracebackType | None = None,
    sender: Task | None = None,
    **_kwargs: dict[str, Any],
) -> None:
    """Log task failure."""
    if task_id and sender:
        logger.error(f"Task failed: {sender.name}[{task_id}]")
        if exception:
            logger.error(f"Error: {exception}")
        if traceback:
            logger.error(f"Traceback: {traceback}")


@task_revoked.connect
def task_revoked_handler(
    request: Request | None = None,
    terminated: bool = False,
    signum: int | None = None,
    **_kwargs: dict[str, Any],
) -> None:
    """Log when task is revoked."""
    if request:
        logger.warning(
            f"Task revoked: {request.task}[{request.id}] "
            f"(terminated: {terminated}, signal: {signum})"
        )


# Configure logging before starting worker
setup_logging()

if __name__ == "__main__":
    celery_app.start()
