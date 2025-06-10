"""Tests for health check functionality."""

from unittest.mock import Mock

import pytest
from celery import Celery
from redis.exceptions import ConnectionError, RedisError

from src.core.health import check_celery_worker, check_redis_connection

# Constants for test values
ACTIVE_WORKERS = 10
ACTIVE_TASKS = 2
RESERVED_TASKS = 3


@pytest.fixture
def mock_redis() -> Mock:
    """Mock Redis client."""
    mock = Mock()
    mock.info.return_value = {"redis_version": "6.2.6"}
    return mock


@pytest.fixture
def mock_celery_app() -> Mock:
    """Mock Celery app."""
    mock = Mock(spec=Celery)
    mock.control = Mock()
    mock.control.inspect.return_value = Mock()
    return mock


def test_check_redis_connection_healthy(mock_redis: Mock) -> None:
    """Test healthy Redis connection."""
    result = check_redis_connection(mock_redis)
    assert result.is_healthy
    assert result.details == {
        "status": "healthy",
        "version": "6.2.6",
    }


def test_check_redis_connection_error(mock_redis: Mock) -> None:
    """Test Redis connection error."""
    mock_redis.info.side_effect = ConnectionError("Connection refused")
    result = check_redis_connection(mock_redis)
    assert not result.is_healthy
    assert result.details == {
        "status": "unhealthy",
        "error": "Connection refused",
    }


def test_check_redis_general_error(mock_redis: Mock) -> None:
    """Test Redis general error."""
    mock_redis.info.side_effect = RedisError("Unknown error")
    result = check_redis_connection(mock_redis)
    assert not result.is_healthy
    assert result.details == {
        "status": "unhealthy",
        "error": "Unknown error",
    }


def test_check_celery_worker_healthy(mock_celery_app: Mock) -> None:
    """Test healthy Celery worker."""
    mock_celery_app.control.inspect.return_value.active.return_value = {
        "worker1": [{"id": f"task{i}"} for i in range(ACTIVE_TASKS)],
        "worker2": [{"id": f"task{i}"} for i in range(RESERVED_TASKS)],
    }
    result = check_celery_worker(mock_celery_app)
    assert result.is_healthy
    assert result.details == {
        "status": "healthy",
        "active_workers": 2,
        "active_tasks": ACTIVE_TASKS + RESERVED_TASKS,
    }


def test_check_celery_worker_no_workers(mock_celery_app: Mock) -> None:
    """Test Celery worker with no active workers."""
    mock_celery_app.control.inspect.return_value.active.return_value = None
    result = check_celery_worker(mock_celery_app)
    assert not result.is_healthy
    assert result.details == {
        "status": "unhealthy",
        "error": "No active workers found",
    }


def test_check_celery_worker_error(mock_celery_app: Mock) -> None:
    """Test Celery worker error."""
    mock_celery_app.control.inspect.side_effect = ConnectionError("Connection refused")
    result = check_celery_worker(mock_celery_app)
    assert not result.is_healthy
    assert result.details == {
        "status": "unhealthy",
        "error": "Connection refused",
    }
