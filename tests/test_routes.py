"""Tests for API routes."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.models import TaskProgress, TaskState, TaskStateInfo
from src.core.storage import JobStorage, SpecFormat
from src.main import app
from src.services.llm import EndpointAnalysis, SpecAnalysis
from tests.conftest import assert_file_exists_with_content

client = TestClient(app)


@pytest.fixture
def mock_state_store() -> Generator[Mock, None, None]:
    """Mock the state store."""
    with patch("src.api.routes.state_store") as mock:
        yield mock


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
        test_job_id: str,
    ) -> None:
        """Test uploading a valid JSON OpenAPI spec"""
        # Create storage instance to ensure directory exists
        storage = JobStorage(test_job_id)

        with patch("src.api.routes.create_processing_chain") as mock_chain:
            mock_chain.return_value.delay.return_value = None
            with patch("src.api.routes.uuid4") as mock_uuid:
                mock_uuid.return_value = test_job_id

                response = client.post(
                    "/api/spec/upload",
                    files={"file": ("test.json", sample_spec, "application/json")},
                )
                assert response.status_code == status.HTTP_200_OK
                assert response.json() == {"job_id": test_job_id}

                # Verify file was saved
                spec_path = storage.job_dir / "spec.json"
                assert_file_exists_with_content(spec_path, sample_spec)

                # Verify chain was created with correct arguments
                mock_chain.assert_called_once_with(
                    sample_spec.decode("utf-8"), test_job_id
                )
                mock_chain.return_value.delay.assert_called_once()

    def test_upload_valid_yaml(
        self: "TestSpecUpload",
        sample_spec: bytes,
        test_job_id: str,
    ) -> None:
        """Test uploading with YAML content type"""
        # Create storage instance to ensure directory exists
        storage = JobStorage(test_job_id)

        with patch("src.api.routes.create_processing_chain") as mock_chain:
            mock_chain.return_value.delay.return_value = None
            with patch("src.api.routes.uuid4") as mock_uuid:
                mock_uuid.return_value = test_job_id

                response = client.post(
                    "/api/spec/upload",
                    files={"file": ("test.yaml", sample_spec, "text/yaml")},
                )
                assert response.status_code == status.HTTP_200_OK
                assert response.json() == {"job_id": test_job_id}

                # Verify file was saved
                spec_path = storage.job_dir / "spec.yaml"
                assert_file_exists_with_content(spec_path, sample_spec)

                # Verify chain was created with correct arguments
                mock_chain.assert_called_once_with(
                    sample_spec.decode("utf-8"), test_job_id
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
        test_job_id: str,
    ) -> None:
        """Test getting a pending summary from state store."""
        mock_state_store.get_state.return_value = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.PROGRESS,
            progress=[
                TaskProgress(
                    stage="test",
                    progress=50.0,
                    message="Test progress",
                )
            ],
        )

        response = client.get(f"/api/spec/{test_job_id}/summary")
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["status"] == "PROGRESS"
        assert response.json()["progress"]["stage"] == "test"

    def test_get_failed_summary_from_state(
        self: "TestSpecSummary",
        mock_state_store: Mock,
        test_job_id: str,
    ) -> None:
        """Test getting a failed summary from state store."""
        mock_state_store.get_state.return_value = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.FAILURE,
            error="Test error",
        )

        response = client.get(f"/api/spec/{test_job_id}/summary")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Test error" in response.json()["detail"]

    def test_get_completed_summary_from_state(
        self: "TestSpecSummary",
        mock_state_store: Mock,
        test_job_id: str,
    ) -> None:
        """Test getting a completed summary from state store."""
        mock_state_store.get_state.return_value = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.SUCCESS,
            result={"test": "result"},
        )

        response = client.get(f"/api/spec/{test_job_id}/summary")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "SUCCESS"
        assert response.json()["result"]["test"] == "result"

    def test_get_pending_summary_fallback(
        self: "TestSpecSummary",
        mock_state_store: Mock,
        test_job_id: str,
    ) -> None:
        """Test falling back to Celery state for pending summary."""
        mock_state_store.get_state.return_value = None

        with patch("src.api.routes.analyze_api_task") as mock_task:
            mock_task.AsyncResult.return_value = Mock(status="PENDING")
            response = client.get(f"/api/spec/{test_job_id}/summary")
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "processing" in response.json()["detail"]


class TestSpecState:
    """Tests for state endpoint."""

    def test_get_state_not_found(
        self: "TestSpecState",
        mock_state_store: Mock,
        test_job_id: str,
    ) -> None:
        """Test getting state for non-existent job."""
        mock_state_store.get_state.return_value = None

        with patch("src.api.routes.analyze_api_task") as mock_task:
            mock_result = Mock(status="PENDING")
            mock_task.AsyncResult.return_value = mock_result

            response = client.get(f"/api/spec/{test_job_id}/state")
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert response.json()["status"] == "PENDING"

    def test_get_state_success(
        self: "TestSpecState",
        mock_state_store: Mock,
        test_job_id: str,
    ) -> None:
        """Test getting state for successful job."""
        mock_state_store.get_state.return_value = TaskStateInfo(
            job_id=test_job_id,
            state=TaskState.SUCCESS,
            result={"test": "result"},
        )

        response = client.get(f"/api/spec/{test_job_id}/state")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "SUCCESS"


class TestSpecExport:
    """Tests for export endpoint."""

    def test_export_nonexistent_job(self: "TestSpecExport", test_job_id: str) -> None:
        """Test exporting a non-existent job"""
        response = client.get(f"/api/spec/{test_job_id}/export")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Job not found" in response.json()["detail"]

    def test_export_markdown(self: "TestSpecExport", test_job_id: str) -> None:
        """Test exporting summary as Markdown"""
        # Create a mock spec file to make the job exist
        storage = JobStorage(test_job_id)
        storage.save_spec("test spec", SpecFormat.JSON)
        storage.save_summary({"test": "summary"})

        response = client.get(f"/api/spec/{test_job_id}/export?file_format=md")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        assert (
            f"api-summary-{test_job_id}.md" in response.headers["content-disposition"]
        )

        # Verify export was saved
        export_path = storage.job_dir / "summary.md"
        assert export_path.exists()

    def test_export_html(self: "TestSpecExport", test_job_id: str) -> None:
        """Test exporting summary as HTML"""
        # Create a mock spec file to make the job exist
        storage = JobStorage(test_job_id)
        storage.save_spec("test spec", SpecFormat.JSON)
        storage.save_summary({"test": "summary"})

        response = client.get(f"/api/spec/{test_job_id}/export?file_format=html")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "<h1>API Summary</h1>" in response.text

        # Verify export was saved
        export_path = storage.job_dir / "summary.html"
        assert export_path.exists()

    def test_export_docx(self: "TestSpecExport", test_job_id: str) -> None:
        """Test exporting summary as DOCX"""
        # Create a mock spec file to make the job exist
        storage = JobStorage(test_job_id)
        storage.save_spec("test spec", SpecFormat.JSON)
        storage.save_summary({"test": "summary"})

        response = client.get(f"/api/spec/{test_job_id}/export?file_format=docx")
        assert response.status_code == status.HTTP_200_OK
        assert (
            "application/vnd.openxmlformats-officedocument"
            in response.headers["content-type"]
        )
        assert (
            f"api-summary-{test_job_id}.docx" in response.headers["content-disposition"]
        )

        # Verify export was saved
        export_path = storage.job_dir / "summary.docx"
        assert export_path.exists()
