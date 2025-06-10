"""Tests for background tasks."""

import json
from collections.abc import Generator

import pytest
from redis import Redis

from src.core.config import settings
from src.core.models import TaskState
from src.core.state import state_store
from src.services.parser import ParsedSpec
from src.tasks.standalone import handle_success


@pytest.fixture(autouse=True)
def use_test_redis(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Use test Redis database."""
    test_redis_url = "redis://localhost:6379/1"  # Use DB 1 for tests
    monkeypatch.setenv("REDIS_URL", test_redis_url)
    monkeypatch.setattr("src.core.config.settings.REDIS_URL", test_redis_url)

    # Store original Redis URL and state store
    original_redis = state_store.redis

    # Update the existing state store's Redis connection
    state_store.redis = Redis.from_url(test_redis_url)
    state_store.redis.flushdb()  # Clean before test

    yield

    # Clean up and restore original state
    state_store.redis.flushdb()  # Clean after test
    state_store.redis = original_redis


@pytest.fixture
def parsed_spec() -> ParsedSpec:
    """Create a parsed spec for testing."""
    return ParsedSpec(
        title="Test API",
        version="1.0.0",
        description=None,
        endpoints=[],
        components={},
    )


@pytest.fixture
def cached_spec() -> dict:
    """Create a cached spec for testing."""
    return {
        "title": "Cached API",
        "version": "1.0.0",
        "description": None,
        "endpoints": [],
        "components": {},
    }


class TestAnalyzeAPITask:
    """Tests for analyze_api_task."""

    def test_handle_success_integration(
        self,
        test_job_id: str,
    ) -> None:
        """Integration test for success handler with real Redis."""
        test_data = {"test": "data"}
        result = {"job_id": test_job_id, "result": test_data}
        handle_success(result=result)

        # Verify state was saved in Redis
        redis = Redis.from_url(settings.REDIS_URL)
        key = f"job:{test_job_id}"
        saved_state = redis.get(key)
        assert saved_state is not None

        state_data = json.loads(saved_state)
        assert state_data["state"] == TaskState.SUCCESS.value
        assert state_data["result"] == result
