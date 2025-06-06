"""Tests for task state management."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from redis import Redis

from src.core.models import TaskState, TaskStateInfo
from src.core.state import StateStore


@pytest.fixture
def state_store() -> StateStore:
    """Create a state store instance."""
    store = StateStore()
    store.redis = Mock(spec=Redis)  # Replace Redis instance with mock
    return store


@pytest.fixture
def job_id() -> str:
    """Create a test job ID."""
    return "test-job-id"


class TestStateStore:
    """Tests for StateStore class."""

    def test_get_state_not_found(self, state_store: StateStore, job_id: str) -> None:
        """Test getting state for non-existent job."""
        state_store.redis.get.return_value = None
        assert state_store.get_state(job_id) is None

    def test_get_state_invalid_json(self, state_store: StateStore, job_id: str) -> None:
        """Test getting state with invalid JSON."""
        state_store.redis.get.return_value = b"invalid json"
        assert state_store.get_state(job_id) is None

    def test_set_state(self, state_store: StateStore, job_id: str) -> None:
        """Test setting state."""
        state = TaskStateInfo(
            job_id=job_id,
            state=TaskState.STARTED,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        state_store.set_state(state)

        state_store.redis.setex.assert_called_once()
        key = f"{state_store.state_prefix}{job_id}"
        assert state_store.redis.setex.call_args[0][0] == key
        assert state_store.redis.setex.call_args[0][1] == int(
            timedelta(days=7).total_seconds()
        )
        saved_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(saved_state, str)
        assert "STARTED" in saved_state
        assert job_id in saved_state

    def test_update_progress(self, state_store: StateStore, job_id: str) -> None:
        """Test updating progress."""
        # Initial state doesn't exist
        state_store.redis.get.return_value = None

        state_store.update_progress(
            job_id=job_id,
            stage="test",
            progress=50.0,
            message="Testing progress",
        )

        # Verify state was created and saved
        state_store.redis.setex.assert_called_once()
        saved_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(saved_state, str)
        assert "PROGRESS" in saved_state
        assert "test" in saved_state
        assert "50.0" in saved_state
        assert "Testing progress" in saved_state

    def test_set_success(self, state_store: StateStore, job_id: str) -> None:
        """Test setting success state."""
        result = {"test": "result"}
        state_store.set_success(job_id, result)

        state_store.redis.setex.assert_called_once()
        saved_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(saved_state, str)
        assert "SUCCESS" in saved_state
        assert "test" in saved_state
        assert "result" in saved_state

    def test_set_failure(self, state_store: StateStore, job_id: str) -> None:
        """Test setting failure state."""
        error = "Test error"
        state_store.set_failure(job_id, error)

        state_store.redis.setex.assert_called_once()
        saved_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(saved_state, str)
        assert "FAILURE" in saved_state
        assert error in saved_state

    def test_set_retry(self, state_store: StateStore, job_id: str) -> None:
        """Test setting retry state."""
        # Set up existing state with retries
        existing_state = TaskStateInfo(
            job_id=job_id,
            state=TaskState.RETRY,
            retries=1,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        state_store.redis.get.return_value = existing_state.model_dump_json()

        error = "Test error"
        state_store.set_retry(job_id, error)

        state_store.redis.setex.assert_called_once()
        saved_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(saved_state, str)
        assert "RETRY" in saved_state
        assert error in saved_state
        assert '"retries": 2' in saved_state  # Verify retry count was incremented

    def test_state_persistence(self, state_store: StateStore, job_id: str) -> None:
        """Test full state persistence flow."""
        # 1. Start job
        state_store.set_started(job_id)
        assert isinstance(state_store.redis.setex.call_args[0][2], str)
        assert "STARTED" in state_store.redis.setex.call_args[0][2]

        # 2. Update progress
        state_store.update_progress(job_id, "stage1", 25.0, "Stage 1")
        progress_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(progress_state, str)
        assert "PROGRESS" in progress_state
        assert "stage1" in progress_state
        assert "25.0" in progress_state

        # 3. Complete successfully
        result = {"test": "complete"}
        state_store.set_success(job_id, result)
        final_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(final_state, str)
        assert "SUCCESS" in final_state
        assert "complete" in final_state
