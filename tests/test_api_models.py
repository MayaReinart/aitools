import pytest
from fastapi import HTTPException, UploadFile
from fastapi import status as http_status

from src.api.models import SummaryResponse, validate_spec_file
from src.core.models import TaskState


def create_upload_file(filename: str, content_type: str) -> UploadFile:
    """Create an UploadFile instance with the given content type."""
    return UploadFile(
        filename=filename,
        file=None,  # type: ignore
        headers={"content-type": content_type},
    )


def test_validate_spec_file_json() -> None:
    """Test validation of JSON spec file."""
    file = create_upload_file("test.json", "application/json")
    validate_spec_file(file)  # Should not raise


def test_validate_spec_file_yaml() -> None:
    """Test validation of YAML spec files."""
    yaml_types = [
        "text/yaml",
        "application/x-yaml",
        "text/x-yaml",
    ]
    for content_type in yaml_types:
        file = create_upload_file("test.yaml", content_type)
        validate_spec_file(file)  # Should not raise


def test_validate_spec_file_invalid() -> None:
    """Test validation of invalid spec file type."""
    file = create_upload_file("test.pdf", "application/pdf")
    with pytest.raises(HTTPException) as exc:
        validate_spec_file(file)
    assert exc.value.status_code == http_status.HTTP_400_BAD_REQUEST
    assert "Unsupported file type" in str(exc.value.detail)


# Constants for test values
TEST_JOB_PROGRESS = 75.5


def test_summary_response_model() -> None:
    """Test SummaryResponse model validation."""
    # Test minimal response
    response = SummaryResponse(status=TaskState.STARTED)
    assert response.status == TaskState.STARTED
    assert response.current_job_name is None
    assert response.current_job_progress is None
    assert response.result is None

    # Test full response
    response = SummaryResponse(
        status=TaskState.SUCCESS,
        current_job_name="test_job",
        current_job_progress=TEST_JOB_PROGRESS,
        result={"test": "data"},
    )
    assert response.status == TaskState.SUCCESS
    assert response.current_job_name == "test_job"
    assert response.current_job_progress == TEST_JOB_PROGRESS
    assert response.result == {"test": "data"}
