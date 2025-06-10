"""Health check utilities."""

from typing import Any

from celery import Celery
from celery.app.control import Inspect
from redis import Redis
from redis.exceptions import ConnectionError, RedisError

from src.core.config import settings


def check_redis_connection() -> tuple[bool, str, dict[str, Any]]:
    """Check Redis connection health."""
    try:
        redis_client = Redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        info = redis_client.info()
        return (
            True,
            "Redis connection is healthy",
            {
                "version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            },
        )
    except ConnectionError:
        return False, "Failed to connect to Redis", {"error": "Connection refused"}
    except RedisError as e:
        return False, f"Redis error: {e!s}", {"error": str(e)}


def check_celery_worker(app: Celery) -> tuple[bool, str, dict[str, Any]]:
    """Check Celery worker health."""
    try:
        inspect: Inspect = app.control.inspect()
        active = inspect.active()

        if not active:
            return (
                False,
                "No Celery workers are running",
                {"error": "No active workers"},
            )

        worker_count = len(active)
        return (
            True,
            "Celery workers are healthy",
            {
                "worker_count": worker_count,
                "active_tasks": sum(len(tasks) for tasks in active.values()),
            },
        )
    except Exception as e:
        return False, f"Failed to check Celery workers: {e!s}", {"error": str(e)}
