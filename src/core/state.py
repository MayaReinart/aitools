"""Task state management using Redis."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from redis import Redis

from src.core.config import settings
from src.core.models import TaskProgress, TaskState, TaskStateInfo


class StateStore:
    """Redis-based task state storage."""

    def __init__(self) -> None:
        """Initialize Redis connection."""
        self.redis = Redis.from_url(settings.REDIS_URL or "redis://localhost:6379/0")
        self.state_prefix = "task_state:"
        self.ttl = timedelta(days=7)  # Store task state for 7 days

    def _get_key(self, job_id: str) -> str:
        """Get Redis key for a job."""
        return f"{self.state_prefix}{job_id}"

    def get_state(self, job_id: str) -> TaskStateInfo | None:
        """Get current state for a job.

        Args:
            job_id: The job identifier

        Returns:
            TaskStateInfo if found, None otherwise
        """
        key = self._get_key(job_id)
        data = self.redis.get(key)
        if not data:
            return None

        try:
            state_dict = json.loads(data)
            return TaskStateInfo.model_validate(state_dict)
        except Exception as e:
            logger.error(f"Error loading state for {job_id}: {e}")
            return None

    def set_state(self, state: TaskStateInfo) -> None:
        """Set state for a job.

        Args:
            state: The state to store
        """
        key = self._get_key(state.job_id)
        state.updated_at = datetime.now(tz=timezone.utc)
        try:
            self.redis.setex(
                key,
                int(self.ttl.total_seconds()),  # Redis expects seconds as int
                json.dumps(state.model_dump()),
            )
        except Exception as e:
            logger.error(f"Error saving state for {state.job_id}: {e}")

    def update_progress(
        self, job_id: str, stage: str, progress: float, message: str
    ) -> None:
        """Update progress for a job.

        Args:
            job_id: The job identifier
            stage: Current processing stage
            progress: Progress percentage (0-100)
            message: Progress message
        """
        state = self.get_state(job_id)
        if not state:
            state = TaskStateInfo(
                job_id=job_id,
                state=TaskState.PROGRESS,
            )

        state.state = TaskState.PROGRESS
        state.progress.append(
            TaskProgress(
                stage=stage,
                progress=progress,
                message=message,
            )
        )
        self.set_state(state)

    def set_started(self, job_id: str) -> None:
        """Mark a job as started.

        Args:
            job_id: The job identifier
        """
        state = TaskStateInfo(
            job_id=job_id,
            state=TaskState.STARTED,
        )
        self.set_state(state)

    def set_success(self, job_id: str, result: dict[str, Any]) -> None:
        """Mark a job as successful.

        Args:
            job_id: The job identifier
            result: The task result
        """
        state = self.get_state(job_id)
        if not state:
            state = TaskStateInfo(
                job_id=job_id,
                state=TaskState.SUCCESS,
            )
        state.state = TaskState.SUCCESS
        state.result = result
        self.set_state(state)

    def set_failure(self, job_id: str, error: str) -> None:
        """Mark a job as failed.

        Args:
            job_id: The job identifier
            error: Error message
        """
        state = self.get_state(job_id)
        if not state:
            state = TaskStateInfo(
                job_id=job_id,
                state=TaskState.FAILURE,
            )
        state.state = TaskState.FAILURE
        state.error = error
        self.set_state(state)

    def set_retry(self, job_id: str, error: str) -> None:
        """Mark a job for retry.

        Args:
            job_id: The job identifier
            error: Error message
        """
        state = self.get_state(job_id)
        if not state:
            state = TaskStateInfo(
                job_id=job_id,
                state=TaskState.RETRY,
            )
        state.state = TaskState.RETRY
        state.error = error
        state.retries += 1
        self.set_state(state)
