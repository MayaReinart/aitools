"""State management for task execution."""

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from pydantic import ValidationError
from redis import Redis
from redis.exceptions import RedisError

from src.core.config import settings
from src.core.models import TaskState, TaskStatus


def _utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class StateStore:
    """Store for task state information."""

    # 24 hours TTL for task states
    TASK_STATE_TTL = 24 * 60 * 60

    def __init__(self) -> None:
        """Initialize the state store."""
        self.redis = Redis.from_url(settings.REDIS_URL)

    def _get_key(self, job_id: str) -> str:
        """Get Redis key for a job."""
        return f"job:{job_id}"

    def get_state(self, job_id: str) -> TaskStatus | None:
        """Get the current state of a job."""
        try:
            key = self._get_key(job_id)
            data = self.redis.get(key)
            if not data:
                return None
            return TaskStatus.model_validate_json(data)
        except (RedisError, ValidationError) as e:
            logger.error(f"Error getting state for job {job_id}: {e}")
            return None

    def set_state(self, state: TaskStatus) -> None:
        """Set the state for a job."""
        try:
            key = self._get_key(state.job_id)
            self.redis.setex(key, self.TASK_STATE_TTL, state.model_dump_json())
        except RedisError as e:
            logger.error(f"Error setting state for job {state.job_id}: {e}")

    def set_task_id(self, job_id: str, task_id: str) -> None:
        """Set the task ID for a job."""
        state = self.get_state(job_id)
        if not state:
            state = TaskStatus(
                job_id=job_id,
                task_id=task_id,
                state=TaskState.STARTED,
            )
        else:
            state.task_id = task_id
            state.updated_at = _utc_now()
        self.set_state(state)

    def set_started(self, job_id: str) -> None:
        """Set a job as started."""
        state = TaskStatus(
            job_id=job_id,
            state=TaskState.STARTED,
        )
        self.set_state(state)

    def set_success(self, job_id: str, result: dict[str, Any]) -> None:
        """Set a job as successful."""
        state = self.get_state(job_id)
        if not state:
            state = TaskStatus(
                job_id=job_id,
                state=TaskState.SUCCESS,
                result=result,
            )
        else:
            state.state = TaskState.SUCCESS
            state.result = result
            state.updated_at = _utc_now()
        self.set_state(state)

    def set_failure(self, job_id: str, error: str) -> None:
        """Set a job as failed."""
        state = self.get_state(job_id)
        if not state:
            state = TaskStatus(
                job_id=job_id,
                state=TaskState.FAILURE,
                error=error,
            )
        else:
            state.state = TaskState.FAILURE
            state.error = error
            state.updated_at = _utc_now()
        self.set_state(state)

    def set_retry(self, job_id: str, error: str) -> None:
        """Set a job as retried, incrementing retry count."""
        state = self.get_state(job_id)
        if not state:
            state = TaskStatus(
                job_id=job_id,
                state=TaskState.FAILURE,
                error=error,
                retries=1,
            )
        else:
            state.state = TaskState.FAILURE
            state.error = error
            state.retries += 1
            state.updated_at = _utc_now()
        self.set_state(state)

    def update_progress(
        self,
        job_id: str,
        stage: str,
        progress: float,
        message: str | None = None,
    ) -> None:
        """Update progress for a job."""
        state = self.get_state(job_id)
        if not state:
            state = TaskStatus(
                job_id=job_id,
                state=TaskState.PROGRESS,
            )
        state.update_progress(stage, progress, message)
        self.set_state(state)


# Global state store instance
state_store = StateStore()
