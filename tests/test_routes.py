"""Tests for API routes."""

from collections.abc import Generator
from pathlib import Path
from shutil import rmtree
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.storage import JOB_DATA_ROOT
from src.main import app

client = TestClient(app)


SAMPLES_PATH = Path(__file__).parent / "samples"


@pytest.fixture
def sample_spec() -> bytes:
    """Load the sample OpenAPI spec for testing"""
    spec_path = SAMPLES_PATH / "sample.json"
    return spec_path.read_bytes()


@pytest.fixture(autouse=True)
def cleanup_job_data() -> Generator[None, None, None]:
    """Clean up job data after each test."""
    yield
    if JOB_DATA_ROOT.exists():
        rmtree(JOB_DATA_ROOT)


def test_health_check() -> None:
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


class TestSpecUpload:
    """Tests for spec upload endpoint."""

    def test_upload_valid_json(self, sample_spec: bytes) -> None:
        """Test uploading a valid JSON OpenAPI spec"""
        with (
            patch("src.api.routes.uuid4") as mock_uuid,
            patch("src.api.routes.summarize_doc_task") as mock_task,
        ):
            mock_uuid.return_value = "test-job-id"

            response = client.post(
                "/api/spec/upload",
                files={"file": ("test.json", sample_spec, "application/json")},
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {"job_id": "test-job-id"}
            mock_task.delay.assert_called_once()

            # Verify file was saved
            spec_path = JOB_DATA_ROOT / "test-job-id" / "spec.json"
            assert spec_path.exists()
            assert spec_path.read_bytes() == sample_spec

    def test_upload_valid_yaml(self, sample_spec: bytes) -> None:
        """Test uploading with YAML content type"""
        with (
            patch("src.api.routes.uuid4") as mock_uuid,
            patch("src.api.routes.summarize_doc_task") as mock_task,
        ):
            mock_uuid.return_value = "test-job-id"

            response = client.post(
                "/api/spec/upload",
                files={"file": ("test.yaml", sample_spec, "text/yaml")},
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {"job_id": "test-job-id"}
            mock_task.delay.assert_called_once()

            # Verify file was saved
            spec_path = JOB_DATA_ROOT / "test-job-id" / "spec.yaml"
            assert spec_path.exists()
            assert spec_path.read_bytes() == sample_spec

    def test_upload_invalid_content_type(self, sample_spec: bytes) -> None:
        """Test uploading file with invalid content type"""
        response = client.post(
            "/api/spec/upload",
            files={"file": ("test.txt", sample_spec, "text/csv")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_no_file(self) -> None:
        """Test uploading without a file"""
        response = client.post("/api/spec/upload")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestSpecSummary:
    def test_get_pending_summary(self) -> None:
        """Test getting summary for a pending job"""
        with patch("src.api.routes.summarize_doc_task") as mock_task:
            mock_task.AsyncResult.return_value = Mock(status="PENDING")
            response = client.get("/api/spec/test-job-id/summary")
            assert response.status_code == status.HTTP_202_ACCEPTED
            assert "processing" in response.json()["detail"]

    def test_get_failed_summary(self) -> None:
        """Test getting summary for a failed job"""
        with patch("src.api.routes.summarize_doc_task") as mock_task:
            mock_task.AsyncResult.return_value = Mock(status="FAILURE")
            response = client.get("/api/spec/test-job-id/summary")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "failed" in response.json()["detail"]

    def test_get_completed_summary(self) -> None:
        """Test getting summary for a completed job"""
        mock_result = {
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

        with patch("src.api.routes.summarize_doc_task") as mock_task:
            mock_task.AsyncResult.return_value = Mock(
                status="SUCCESS", result=mock_result
            )
            response = client.get("/api/spec/test-job-id/summary")
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {
                "status": "SUCCESS",
                "result": mock_result,
            }

            # Verify summary was saved
            summary_path = JOB_DATA_ROOT / "test-job-id" / "summary.json"
            assert summary_path.exists()


class TestSpecExport:
    def test_export_nonexistent_job(self) -> None:
        """Test exporting a non-existent job"""
        response = client.get("/api/spec/nonexistent-id/export")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Job not found" in response.json()["detail"]

    def test_export_markdown(self) -> None:
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

    def test_export_html(self) -> None:
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

    def test_export_docx(self) -> None:
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
