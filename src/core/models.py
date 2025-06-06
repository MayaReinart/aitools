"""Task state and progress models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_serializer


class DateTimeSerializerMixin(BaseModel):
    """Mixin to handle datetime ISO format serialization."""

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize the model, converting all datetime fields to ISO format."""
        data: dict[str, Any] = {}
        for field_name, field_value in self:
            if isinstance(field_value, datetime):
                data[field_name] = field_value.isoformat()
            elif (
                isinstance(field_value, list)
                and field_value
                and isinstance(field_value[0], BaseModel)
            ):
                data[field_name] = [
                    dict(item.model_dump(mode="json")) for item in field_value
                ]
            elif isinstance(field_value, Enum):
                data[field_name] = field_value.value
            elif field_value is not None:
                data[field_name] = field_value
        return data


class TaskState(str, Enum):
    """Task execution states."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"


class TaskProgress(DateTimeSerializerMixin):
    """Task progress information."""

    stage: str = Field(..., description="Current processing stage")
    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    message: str = Field(..., description="Progress message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class TaskStateInfo(DateTimeSerializerMixin):
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
