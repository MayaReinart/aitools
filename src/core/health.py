"""Health check utilities."""

from dataclasses import dataclass
from typing import Any

from celery import Celery
from celery.app.control import Inspect
from redis import Redis
from redis.exceptions import ConnectionError, RedisError

from src.core.config import settings


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    is_healthy: bool
    details: dict[str, Any]


def check_redis_connection(redis_client: Redis | None = None) -> HealthCheckResult:
    """Check Redis connection health."""
    if redis_client is None:
        redis_client = Redis.from_url(settings.REDIS_URL)

    try:
        redis_client.ping()
        info = redis_client.info()
        return HealthCheckResult(
            is_healthy=True,
            details={
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),  # type: ignore[union-attr]
                # Item "Awaitable[Any]" of "Awaitable[Any] | Any" has no attribute "get"
            },
        )
    except ConnectionError:
        return HealthCheckResult(
            is_healthy=False,
            details={
                "status": "unhealthy",
                "error": "Connection refused",
            },
        )
    except RedisError as e:
        return HealthCheckResult(
            is_healthy=False,
            details={
                "status": "unhealthy",
                "error": str(e),
            },
        )


def check_celery_worker(app: Celery) -> HealthCheckResult:
    """Check Celery worker health."""
    try:
        inspect: Inspect = app.control.inspect()
        active = inspect.active()

        if not active:
            return HealthCheckResult(
                is_healthy=False,
                details={
                    "status": "unhealthy",
                    "error": "No active workers found",
                },
            )

        worker_count = len(active)
        active_tasks = sum(len(tasks) for tasks in active.values())
        return HealthCheckResult(
            is_healthy=True,
            details={
                "status": "healthy",
                "active_workers": worker_count,
                "active_tasks": active_tasks,
            },
        )
    except Exception as e:
        return HealthCheckResult(
            is_healthy=False,
            details={
                "status": "unhealthy",
                "error": str(e),
            },
        )
