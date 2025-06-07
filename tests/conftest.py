"""Test configuration."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage
from redis import Redis
from redis.exceptions import ConnectionError

from celery_worker import celery_app
from src.core.models import TaskProgress, TaskState, TaskStateInfo
from src.core.state import StateStore
from src.core.storage import JobStorage
from src.services.llm import EndpointAnalysis, SpecAnalysis

SAMPLES_PATH = Path(__file__).parent / "samples"
TEST_TIMESTAMP = datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def check_redis_connection() -> None:
    """Check Redis connection before running tests."""
    try:
        redis = Redis.from_url("redis://localhost:6379/0")
        redis.ping()
    except ConnectionError as e:
        pytest.exit(f"Redis connection failed: {e}. Please ensure Redis is running.")


@pytest.fixture(autouse=True)
def temp_job_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a temporary directory for job data in tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        # Patch before any imports or storage creation
        monkeypatch.setattr("src.core.storage.JOB_DATA_ROOT", temp_path)
        yield


def pytest_configure() -> None:
    """Configure test environment."""
    # Configure Celery for testing before any tests run
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="redis://",
        task_always_eager=True,
        task_store_eager_result=True,
        broker_connection_retry=False,
        broker_connection_max_retries=0,
        task_remote_tracebacks=True,  # For better error messages
    )


@pytest.fixture
def mock_redis() -> Mock:
    """Create a mock Redis instance for unit tests."""
    redis = Mock(spec=Redis)
    redis.get.return_value = None  # Default to no state
    redis.setex.return_value = True  # Default behavior for setting keys
    return redis


@pytest.fixture
def state_store(mock_redis: Mock) -> StateStore:
    """Create a state store instance with mock Redis."""
    store = StateStore()
    store.redis = mock_redis
    return store


@pytest.fixture
def mock_state_info(test_job_id: str) -> TaskStateInfo:
    """Create a mock task state info."""
    return TaskStateInfo(
        job_id=test_job_id,
        state=TaskState.SUCCESS,
        result={"test": "result"},
        created_at=TEST_TIMESTAMP,
        updated_at=TEST_TIMESTAMP,
    )


def assert_redis_state(
    redis_mock: Mock,
    expected_state: TaskStateInfo | None,
    key_prefix: str = "task_state:",
) -> None:
    """Assert Redis state was set correctly.

    Args:
        redis_mock: Mock Redis instance
        expected_state: Expected state or None
        key_prefix: Redis key prefix
    """
    if expected_state is None:
        redis_mock.setex.assert_not_called()
        return

    assert redis_mock.setex.call_count > 0, "Expected Redis setex to be called"
    # Get the most recent call
    last_call = redis_mock.setex.call_args
    key = f"{key_prefix}{expected_state.job_id}"
    assert last_call[0][0] == key
    saved_state = last_call[0][2]
    assert isinstance(saved_state, str)
    assert expected_state.state.value in saved_state
    assert expected_state.job_id in saved_state


@pytest.fixture
def sample_spec() -> bytes:
    """Load the sample OpenAPI spec for testing."""
    spec_path = SAMPLES_PATH / "sample.json"
    return spec_path.read_bytes()


@pytest.fixture
def test_job_id() -> str:
    """Create a consistent test job ID."""
    return "test-job-id"


@pytest.fixture
def mock_storage(test_job_id: str) -> Mock:
    """Create a mock storage instance."""
    storage = Mock(spec=JobStorage)
    storage.job_id = test_job_id
    return storage


@pytest.fixture
def mock_progress() -> TaskProgress:
    """Create a mock task progress."""
    return TaskProgress(
        stage="test",
        progress=50.0,
        message="Test progress",
        timestamp=TEST_TIMESTAMP,
    )


def create_mock_chat_completion(content: str) -> ChatCompletion:
    """Create a mock ChatCompletion object."""
    return ChatCompletion(
        id="mock-completion",
        model="gpt-4",
        object="chat.completion",
        created=1234567890,
        choices=[
            {
                "finish_reason": "stop",
                "index": 0,
                "message": ChatCompletionMessage(
                    role="assistant",
                    content=content,
                ),
            }
        ],
        usage=CompletionUsage(
            completion_tokens=100,
            prompt_tokens=100,
            total_tokens=200,
        ),
    )


@pytest.fixture
def mock_spec_analysis() -> SpecAnalysis:
    """Create a mock spec analysis result."""
    return SpecAnalysis(
        overview="Test API overview",
        endpoints=[
            EndpointAnalysis(
                path="/test",
                method="GET",
                analysis="Test endpoint analysis",
            )
        ],
    )


@pytest.fixture
def mock_upload_file() -> UploadFile:
    """Create a mock upload file."""
    return UploadFile(
        filename="test.json",
        file=None,
        content_type="application/json",
        headers={"content-type": "application/json"},
    )


def assert_file_exists_with_content(path: Path, expected_content: str | bytes) -> None:
    """Assert file exists and has expected content."""
    assert path.exists(), f"File {path} does not exist"
    content = (
        path.read_bytes() if isinstance(expected_content, bytes) else path.read_text()
    )
    assert content == expected_content, f"File {path} content does not match expected"
