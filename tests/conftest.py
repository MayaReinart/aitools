"""Test configuration."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

from celery_worker import celery_app
from src.core.models import TaskProgress, TaskState, TaskStateInfo
from src.core.storage import JOB_DATA_ROOT, JobStorage
from src.services.llm import EndpointAnalysis, SpecAnalysis

SAMPLES_PATH = Path(__file__).parent / "samples"
TEST_TIMESTAMP = datetime(2024, 1, 1, tzinfo=timezone.utc)


def pytest_configure() -> None:
    """Configure test environment."""
    # Configure Celery for testing before any tests run
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=True,
        task_store_eager_result=True,
        broker_connection_retry=False,
        broker_connection_max_retries=0,
        task_remote_tracebacks=True,  # For better error messages
    )


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
def mock_state() -> TaskStateInfo:
    """Create a mock task state."""
    return TaskStateInfo(
        job_id="test-job-id",
        state=TaskState.SUCCESS,
        result={"test": "result"},
        created_at=TEST_TIMESTAMP,
        updated_at=TEST_TIMESTAMP,
    )


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


@pytest.fixture(autouse=True)
def cleanup_job_data() -> None:
    """Clean up job data after each test."""
    yield
    if JOB_DATA_ROOT.exists():
        JOB_DATA_ROOT.unlink(missing_ok=True)


def assert_file_exists_with_content(path: Path, expected_content: str | bytes) -> None:
    """Assert file exists and has expected content."""
    assert path.exists(), f"File {path} does not exist"
    content = (
        path.read_bytes() if isinstance(expected_content, bytes) else path.read_text()
    )
    assert content == expected_content, f"File {path} content does not match expected"
