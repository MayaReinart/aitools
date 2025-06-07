"""Tests for task state management."""

from unittest.mock import Mock

import pytest
from redis import Redis

from src.core.models import TaskProgress, TaskState, TaskStateInfo
from src.core.state import StateStore
from tests.conftest import TEST_TIMESTAMP, assert_redis_state


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

    def test_get_state_not_found(
        self, state_store: StateStore, test_job_id: str
    ) -> None:
        """Test getting state for non-existent job."""
        state_store.redis.get.return_value = None
        assert state_store.get_state(test_job_id) is None

    def test_get_state_invalid_json(
        self, state_store: StateStore, test_job_id: str
    ) -> None:
        """Test getting state with invalid JSON."""
        state_store.redis.get.return_value = b"invalid json"
        assert state_store.get_state(test_job_id) is None

    def test_set_state(
        self, state_store: StateStore, mock_state_info: TaskStateInfo
    ) -> None:
        """Test setting state."""
        state_store.set_state(mock_state_info)
        assert_redis_state(state_store.redis, mock_state_info)

    def test_update_progress(
        self, state_store: StateStore, test_job_id: str, mock_progress: TaskProgress
    ) -> None:
        """Test updating progress."""
        # Initial state doesn't exist
        state_store.redis.get.return_value = None

        state_store.update_progress(
            job_id=test_job_id,
            stage=mock_progress.stage,
            progress=mock_progress.progress,
            message=mock_progress.message,
        )

        # Verify state was created and saved
        state_store.redis.setex.assert_called_once()
        saved_state = state_store.redis.setex.call_args[0][2]
        assert isinstance(saved_state, str)
        assert TaskState.PROGRESS.value in saved_state
        assert mock_progress.stage in saved_state
        assert str(mock_progress.progress) in saved_state
        assert mock_progress.message in saved_state

    def test_set_success(self, state_store: StateStore, test_job_id: str) -> None:
        """Test setting success state."""
        result = {"test": "result"}
        state_store.set_success(test_job_id, result)

        expected_state = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.SUCCESS,
            result=result,
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        assert_redis_state(state_store.redis, expected_state)

    def test_set_failure(self, state_store: StateStore, test_job_id: str) -> None:
        """Test setting failure state."""
        error = "Test error"
        state_store.set_failure(test_job_id, error)

        expected_state = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.FAILURE,
            error=error,
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        assert_redis_state(state_store.redis, expected_state)

    def test_set_retry(self, state_store: StateStore, test_job_id: str) -> None:
        """Test setting retry state."""
        # Set up existing state with retries
        existing_state = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.RETRY,
            retries=1,
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        state_store.redis.get.return_value = existing_state.model_dump_json()

        error = "Test error"
        state_store.set_retry(test_job_id, error)

        expected_state = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.RETRY,
            error=error,
            retries=2,  # Incremented
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        assert_redis_state(state_store.redis, expected_state)

    def test_state_persistence(self, state_store: StateStore, test_job_id: str) -> None:
        """Test full state persistence flow."""
        # 1. Start job
        state_store.set_started(test_job_id)
        expected_started = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.STARTED,
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        assert_redis_state(state_store.redis, expected_started)

        # 2. Update progress
        progress = TaskProgress(
            stage="stage1",
            progress=25.0,
            message="Stage 1",
            timestamp=TEST_TIMESTAMP,
        )
        state_store.update_progress(
            test_job_id,
            stage=progress.stage,
            progress=progress.progress,
            message=progress.message,
        )
        expected_progress = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.PROGRESS,
            progress=[progress],  # Progress should be a list
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        assert_redis_state(state_store.redis, expected_progress)

        # 3. Complete successfully
        result = {"test": "complete"}
        state_store.set_success(test_job_id, result)
        expected_success = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.SUCCESS,
            result=result,
            created_at=TEST_TIMESTAMP,
            updated_at=TEST_TIMESTAMP,
        )
        assert_redis_state(state_store.redis, expected_success)
