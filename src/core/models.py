"""Task state and progress models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_serializer


class TaskState(str, Enum):
    """Task execution states."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"


class TaskProgress(BaseModel):
    """Task progress information."""

    stage: str = Field(..., description="Current processing stage")
    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    message: str = Field(..., description="Progress message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize the model, converting datetime to ISO format."""
        return {
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


class TaskStateInfo(BaseModel):
    """Complete task state information."""

    job_id: str = Field(..., description="Unique job identifier")
    state: TaskState = Field(..., description="Current task state")
    progress: list[TaskProgress] = Field(
        default_factory=list, description="Progress history"
    )
    result: dict[str, Any] | None = Field(
        default=None, description="Task result if completed"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    retries: int = Field(default=0, description="Number of retries attempted")

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize the model, converting datetime to ISO format."""
        return {
            "job_id": self.job_id,
            "state": self.state,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "retries": self.retries,
        }
