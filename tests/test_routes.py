from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


@pytest.fixture
def sample_spec() -> bytes:
    """Load the sample OpenAPI spec for testing"""
    spec_path = Path(__file__).parent / "sample.json"
    return spec_path.read_bytes()


def test_health_check() -> None:
    """Test the health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}


class TestSpecUpload:
    def test_upload_valid_json(self, sample_spec: bytes) -> None:
        """Test uploading a valid JSON OpenAPI spec"""
        with patch("src.api.routes.summarize_doc_task") as mock_task:
            mock_task.delay.return_value = "test-job-id"
            response = client.post(
                "/api/spec/upload",
                files={"file": ("test.json", sample_spec, "application/json")},
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {"job_id": "test-job-id"}
            mock_task.delay.assert_called_once()

    def test_upload_valid_yaml(self, sample_spec: bytes) -> None:
        """Test uploading with YAML content type"""
        with patch("src.api.routes.summarize_doc_task") as mock_task:
            mock_task.delay.return_value = "test-job-id"
            response = client.post(
                "/api/spec/upload",
                files={"file": ("test.yaml", sample_spec, "text/yaml")},
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {"job_id": "test-job-id"}

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
        with patch("src.api.routes.summarize_doc_task") as mock_task:
            mock_task.AsyncResult.return_value = Mock(
                status="SUCCESS", result={"summary": "Test summary"}
            )
            response = client.get("/api/spec/test-job-id/summary")
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {
                "status": "SUCCESS",
                "result": {"summary": "Test summary"},
            }


class TestSpecExport:
    @pytest.fixture(autouse=True)
    def setup_results_dir(self) -> None:
        """Create temporary results directory for tests"""
        results_dir = Path("results/test-job-id")
        results_dir.mkdir(parents=True, exist_ok=True)
        yield
        # Cleanup after tests
        if results_dir.exists():
            for f in results_dir.glob("*"):
                f.unlink()
            results_dir.rmdir()

    def test_export_markdown(self) -> None:
        """Test exporting summary as Markdown"""
        response = client.get("/api/spec/test-job-id/export?file_format=markdown")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        assert "api-summary-test-job-id.md" in response.headers["content-disposition"]

    def test_export_html(self) -> None:
        """Test exporting summary as HTML"""
        response = client.get("/api/spec/test-job-id/export?file_format=html")
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "<h1>API Summary</h1>" in response.text

    def test_export_docx(self) -> None:
        """Test exporting summary as DOCX"""
        response = client.get("/api/spec/test-job-id/export?file_format=docx")
        assert response.status_code == status.HTTP_200_OK
        assert (
            "application/vnd.openxmlformats-officedocument"
            in response.headers["content-type"]
        )
        assert "api-summary-test-job-id.docx" in response.headers["content-disposition"]
