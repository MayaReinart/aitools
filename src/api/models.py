from typing import Any

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel

from src.core.models import TaskState

CONTENT_TYPES = [
    "application/json",
    "text/yaml",
    "application/x-yaml",
    "text/plain",
    "text/x-yaml",
]


def validate_spec_file(file: UploadFile) -> None:
    """
    Validate an uploaded OpenAPI spec file.

    Args:
        file: The uploaded file to validate

    Raises:
        HTTPException: If the file type is not supported
    """
    if file.content_type not in CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Please upload a JSON or YAML file.",
        )


class SummaryResponse(BaseModel):
    status: TaskState
    current_job_name: str | None = None
    current_job_progress: float | None = None
    result: dict[str, Any] | None = None
