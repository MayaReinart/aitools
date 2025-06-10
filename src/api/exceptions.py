from typing import NoReturn

from fastapi import HTTPException, status
from loguru import logger

from src.core.state import state_store


class APIError(Exception):
    """Base class for API errors."""

    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidFormatError(APIError):
    """Error for invalid file format."""

    def __init__(self) -> None:
        super().__init__(
            "Upload requires JSON or YAML file",
            status.HTTP_400_BAD_REQUEST,
        )


class UploadError(APIError):
    """Error during file upload processing."""

    def __init__(self) -> None:
        super().__init__(
            "Task chain started but no task ID was returned",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class BrokerError(APIError):
    """Error connecting to message broker."""

    def __init__(self) -> None:
        super().__init__(
            "Message broker connection failed",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _raise_http_error(e: APIError) -> NoReturn:
    """Raise HTTPException from APIError."""
    raise HTTPException(status_code=e.status_code, detail=e.message) from e


def handle_upload_error(e: Exception, job_id: str | None = None) -> NoReturn:
    """Handle upload errors uniformly."""
    if isinstance(e, APIError):
        if job_id:
            state_store.set_failure(job_id, e.message)
        _raise_http_error(e)

    # Unexpected error
    error_msg = "Failed to process spec"
    logger.error(f"Error in task chain setup: {e}", exc_info=True)
    if job_id:
        state_store.set_failure(job_id, error_msg)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=error_msg,
    ) from e
