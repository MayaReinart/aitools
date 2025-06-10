"""Tests for background tasks."""

import json

import pytest
from redis import Redis

from src.core.models import TaskState
from src.services.parser import ParsedSpec
from src.tasks.standalone import handle_success


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
        result = {"job_id": test_job_id, **test_data}
        handle_success(result=result)

        # Verify state was saved in Redis
        redis = Redis.from_url("redis://localhost:6379/0")
        key = f"job:{test_job_id}"
        saved_state = redis.get(key)
        assert saved_state is not None
        state_data = json.loads(saved_state)
        assert state_data["state"] == TaskState.SUCCESS.value
        assert state_data["job_id"] == test_job_id
        assert (
            state_data["result"] == result
        )  # Compare with full result including job_id
