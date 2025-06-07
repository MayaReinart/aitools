"""Tests for API routes."""

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from shutil import rmtree
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

from src.core.models import TaskProgress, TaskState, TaskStateInfo
from src.core.storage import JOB_DATA_ROOT
from src.main import app
from src.services.llm import EndpointAnalysis, SpecAnalysis

client = TestClient(app)


SAMPLES_PATH = Path(__file__).parent / "samples"


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
def sample_spec() -> bytes:
    """Load the sample OpenAPI spec for testing"""
    spec_path = SAMPLES_PATH / "sample.json"
    return spec_path.read_bytes()


@pytest.fixture
def mock_state_store() -> Generator[Mock, None, None]:
    """Mock the state store."""
    with patch("src.api.routes.state_store") as mock:
        yield mock


@pytest.fixture(autouse=True)
def cleanup_job_data() -> Generator[None, None, None]:
    """Clean up job data after each test."""
    yield
    if JOB_DATA_ROOT.exists():
        rmtree(JOB_DATA_ROOT)


@pytest.fixture(autouse=True)
def mock_openai() -> Generator[Mock, None, None]:
    """Mock OpenAI API calls."""
    mock_analysis = SpecAnalysis(
        overview="Test API overview",
        endpoints=[
            EndpointAnalysis(
                path="/test", method="GET", analysis="Test endpoint analysis"
            )
        ],
    )
    with patch(
        "src.services.llm.get_llm_spec_analysis", return_value=mock_analysis
    ) as mock:
        yield mock


def test_health_check() -> None:
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


class TestSpecUpload:
    """Tests for spec upload endpoint."""

    def test_upload_valid_json(
        self: "TestSpecUpload",
        sample_spec: bytes,
    ) -> None:
        """Test uploading a valid JSON OpenAPI spec"""
        with patch("src.api.routes.create_processing_chain") as mock_chain:
            mock_chain.return_value.delay.return_value = None
            with patch("src.api.routes.uuid4") as mock_uuid:
                mock_uuid.return_value = "test-job-id"

                response = client.post(
                    "/api/spec/upload",
                    files={"file": ("test.json", sample_spec, "application/json")},
                )
                assert response.status_code == status.HTTP_200_OK
                assert response.json() == {"job_id": "test-job-id"}

                # Verify file was saved
                spec_path = JOB_DATA_ROOT / "test-job-id" / "spec.json"
                assert spec_path.exists()
                assert spec_path.read_bytes() == sample_spec

                # Verify chain was created with correct arguments
                mock_chain.assert_called_once_with(
                    sample_spec.decode("utf-8"), "test-job-id"
                )
                mock_chain.return_value.delay.assert_called_once()

    def test_upload_valid_yaml(
        self: "TestSpecUpload",
        sample_spec: bytes,
    ) -> None:
        """Test uploading with YAML content type"""
        with patch("src.api.routes.create_processing_chain") as mock_chain:
            mock_chain.return_value.delay.return_value = None
            with patch("src.api.routes.uuid4") as mock_uuid:
                mock_uuid.return_value = "test-job-id"

                response = client.post(
                    "/api/spec/upload",
                    files={"file": ("test.yaml", sample_spec, "text/yaml")},
                )
                assert response.status_code == status.HTTP_200_OK
                assert response.json() == {"job_id": "test-job-id"}

                # Verify file was saved
                spec_path = JOB_DATA_ROOT / "test-job-id" / "spec.yaml"
                assert spec_path.exists()
                assert spec_path.read_bytes() == sample_spec

                # Verify chain was created with correct arguments
                mock_chain.assert_called_once_with(
                    sample_spec.decode("utf-8"), "test-job-id"
                )
                mock_chain.return_value.delay.assert_called_once()

    def test_upload_invalid_content_type(
        self: "TestSpecUpload",
        sample_spec: bytes,
    ) -> None:
        """Test uploading file with invalid content type"""
        response = client.post(
            "/api/spec/upload",
            files={"file": ("test.txt", sample_spec, "text/csv")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_no_file(self: "TestSpecUpload") -> None:
        """Test uploading without a file"""
        response = client.post("/api/spec/upload")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSpecSummary:
    """Tests for summary endpoint."""

    def test_get_pending_summary_from_state(
        self: "TestSpecSummary",
        mock_state_store: Mock,
    ) -> None:
        """Test getting summary for a pending job from state store."""
        progress = 50.0

        state = TaskStateInfo(
            job_id="test-job-id",
            state=TaskState.PROGRESS,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
            progress=[
                TaskProgress(
                    stage="parsing",
                    progress=progress,
                    message="Parsing spec",
                    timestamp=datetime.now(tz=timezone.utc),
                )
            ],
        )
        mock_state_store.get_state.return_value = state

        response = client.get("/api/spec/test-job-id/summary")
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["status"] == "PROGRESS"
        assert response.json()["progress"]["stage"] == "parsing"
        assert response.json()["progress"]["progress"] == progress

    def test_get_failed_summary_from_state(
        self: "TestSpecSummary",
        mock_state_store: Mock,
    ) -> None:
        """Test getting summary for a failed job from state store."""
        state = TaskStateInfo(
            job_id="test-job-id",
            state=TaskState.FAILURE,
            error="Test error",
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_state_store.get_state.return_value = state

        response = client.get("/api/spec/test-job-id/summary")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Test error" in response.json()["detail"]

    def test_get_completed_summary_from_state(
        self: "TestSpecSummary",
        mock_state_store: Mock,
    ) -> None:
        """Test getting summary for a completed job from state store."""
        result = {
            "spec_info": {
                "title": "Test API",
                "version": "1.0.0",
                "description": "Test description",
            },
            "summary": {
                "overview": "Test overview",
                "endpoints": [
                    {
                        "path": "/test",
                        "method": "GET",
                        "analysis": "Test endpoint analysis",
                    }
                ],
            },
            "endpoints": [
                {
                    "path": "/test",
                    "method": "GET",
                    "summary": "Test endpoint",
                }
            ],
        }

        state = TaskStateInfo(
            job_id="test-job-id",
            state=TaskState.SUCCESS,
            result=result,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_state_store.get_state.return_value = state

        response = client.get("/api/spec/test-job-id/summary")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "SUCCESS"
        assert response.json()["result"] == result

    def test_get_pending_summary_fallback(
        self: "TestSpecSummary",
        mock_state_store: Mock,
    ) -> None:
        """Test falling back to Celery state when no state store entry exists."""
        mock_state_store.get_state.return_value = None

        with patch("src.api.routes.analyze_api_task") as mock_task:
            mock_task.AsyncResult.return_value = Mock(status="PENDING")
            response = client.get("/api/spec/test-job-id/summary")
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "processing" in response.json()["detail"]


class TestSpecState:
    """Tests for state endpoint."""

    def test_get_state_not_found(
        self: "TestSpecState",
        mock_state_store: Mock,
    ) -> None:
        """Test getting state for non-existent job."""
        mock_state_store.get_state.return_value = None

        with patch("src.api.routes.analyze_api_task") as mock_task:
            mock_result = Mock(status="PENDING")
            mock_task.AsyncResult.return_value = mock_result

            response = client.get("/api/spec/test-job-id/state")
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert response.json()["status"] == "PENDING"

    def test_get_state_success(
        self: "TestSpecState",
        mock_state_store: Mock,
    ) -> None:
        """Test getting state for existing job."""
        state = TaskStateInfo(
            job_id="test-job-id",
            state=TaskState.SUCCESS,
            result={"test": "result"},
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
        )
        mock_state_store.get_state.return_value = state

        response = client.get("/api/spec/test-job-id/state")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "SUCCESS"
        assert response.json()["result"] == {"test": "result"}


class TestSpecExport:
    """Tests for export endpoint."""

    def test_export_nonexistent_job(self: "TestSpecExport") -> None:
        """Test exporting a non-existent job"""
        response = client.get("/api/spec/nonexistent-id/export")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Job not found" in response.json()["detail"]

    def test_export_markdown(self: "TestSpecExport") -> None:
        """Test exporting summary as Markdown"""
        # Create a mock spec file to make the job exist
        job_dir = JOB_DATA_ROOT / "test-job-id"
        job_dir.mkdir(parents=True)
        (job_dir / "spec.json").write_text("{}")

        response = client.get("/api/spec/test-job-id/export?file_format=md")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        assert "api-summary-test-job-id.md" in response.headers["content-disposition"]

        # Verify export was saved
        export_path = job_dir / "summary.md"
        assert export_path.exists()

    def test_export_html(self: "TestSpecExport") -> None:
        """Test exporting summary as HTML"""
        # Create a mock spec file to make the job exist
        job_dir = JOB_DATA_ROOT / "test-job-id"
        job_dir.mkdir(parents=True)
        (job_dir / "spec.json").write_text("{}")

        response = client.get("/api/spec/test-job-id/export?file_format=html")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "<h1>API Summary</h1>" in response.text

        # Verify export was saved
        export_path = job_dir / "summary.html"
        assert export_path.exists()

    def test_export_docx(self: "TestSpecExport") -> None:
        """Test exporting summary as DOCX"""
        # Create a mock spec file to make the job exist
        job_dir = JOB_DATA_ROOT / "test-job-id"
        job_dir.mkdir(parents=True)
        (job_dir / "spec.json").write_text("{}")

        response = client.get("/api/spec/test-job-id/export?file_format=docx")
        assert response.status_code == status.HTTP_200_OK
        assert (
            "application/vnd.openxmlformats-officedocument"
            in response.headers["content-type"]
        )
        assert "api-summary-test-job-id.docx" in response.headers["content-disposition"]

        # Verify export was saved
        export_path = job_dir / "summary.docx"
        assert export_path.exists()
