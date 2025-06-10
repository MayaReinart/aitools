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

    STARTED = "started"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"


def _utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class ProgressUpdate(DateTimeSerializerMixin):
    """Task progress update."""

    stage: str = Field(..., description="Current processing stage")
    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    message: str | None = Field(default=None, description="Progress message")
    timestamp: datetime = Field(default_factory=_utc_now)

    def __str__(self) -> str:
        """Return a string representation of the progress update."""
        return f"""
ProgressUpdate:
    stage={self.stage},
    progress={int(self.progress)},
    message={self.message},
    time={self.timestamp.isoformat()})
"""

    def __repr__(self) -> str:
        """Return a string representation of the progress update."""
        return self.__str__()


class TaskStatus(BaseModel):
    """Task status model."""

    job_id: str
    task_id: str | None = None
    state: TaskState
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    progress: list[ProgressUpdate] = Field(default_factory=list)
    error: str | None = None
    result: dict[str, Any] | None = None
    retries: int = Field(default=0, description="Number of retries attempted")

    def update_progress(
        self,
        stage: str,
        progress: float,
        message: str | None = None,
    ) -> None:
        """Update task progress."""
        self.progress.append(
            ProgressUpdate(stage=stage, progress=progress, message=message)
        )
        self.updated_at = _utc_now()

    @property
    def latest_progress(self) -> ProgressUpdate | None:
        """Get the latest progress update."""
        return self.progress[-1] if self.progress else None

    @property
    def progress_stages(self) -> list[str]:
        """Get unique stages in progress."""
        return list({update.stage for update in self.progress})

    @property
    def stage_progress(self) -> dict[str, float]:
        """Get progress by stage."""
        return {
            stage: next(
                (
                    update.progress
                    for update in reversed(self.progress)
                    if update.stage == stage
                ),
                0.0,
            )
            for stage in self.progress_stages
        }
