"""Task state management using Redis."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from redis import Redis
from redis.exceptions import ConnectionError, RedisError

from src.core.config import settings
from src.core.models import TaskProgress, TaskState, TaskStateInfo


class StateStore:
    """Redis-based task state storage."""

    def __init__(self) -> None:
        """Initialize Redis connection."""
        self.redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
        logger.info(f"Initializing Redis connection to {self.redis_url}")
        try:
            self.redis = Redis.from_url(self.redis_url)
            # Test connection
            self.redis.ping()
            logger.info("Successfully connected to Redis")
        except ConnectionError as e:
            logger.error(f"Failed to connect to Redis at {self.redis_url}: {e!s}")
            raise
        except RedisError as e:
            logger.error(f"Redis error during initialization: {e!s}")
            raise

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
        logger.debug(f"Fetching state for job {job_id}")
        try:
            data = self.redis.get(key)
            if not data:
                logger.debug(f"No state found for job {job_id}")
                return None

            state_dict = json.loads(data)
            return TaskStateInfo.model_validate(state_dict)
        except ConnectionError as e:
            logger.error(
                f"Redis connection error while getting state for {job_id}: {e!s}"
            )
            raise
        except RedisError as e:
            logger.error(f"Redis error while getting state for {job_id}: {e!s}")
            raise
        except Exception as e:
            logger.error(f"Error loading state for {job_id}: {e!s}", exc_info=True)
            return None

    def set_state(self, state: TaskStateInfo) -> None:
        """Set state for a job.

        Args:
            state: The state to store
        """
        key = self._get_key(state.job_id)
        state.updated_at = datetime.now(tz=timezone.utc)
        logger.debug(f"Setting state for job {state.job_id}: {state.state}")
        try:
            self.redis.setex(
                key,
                int(self.ttl.total_seconds()),  # Redis expects seconds as int
                json.dumps(state.model_dump()),
            )
            logger.debug(f"Successfully set state for job {state.job_id}")
        except ConnectionError as e:
            logger.error(
                f"Redis connection error while setting state for {state.job_id}: {e!s}"
            )
            raise
        except RedisError as e:
            logger.error(f"Redis error while setting state for {state.job_id}: {e!s}")
            raise
        except Exception as e:
            logger.error(f"Error saving state for {state.job_id}: {e!s}", exc_info=True)
            raise

    def set_started(self, job_id: str) -> None:
        """Set job state to started."""
        logger.info(f"Setting job {job_id} state to STARTED")
        state = TaskStateInfo(
            job_id=job_id,
            state=TaskState.STARTED,
            created_at=datetime.now(tz=timezone.utc),
            updated_at=datetime.now(tz=timezone.utc),
            progress=[],
        )
        self.set_state(state)

    def set_success(self, job_id: str, result: dict[str, Any]) -> None:
        """Set job state to success."""
        logger.info(f"Setting job {job_id} state to SUCCESS")
        current_state = self.get_state(job_id)
        if not current_state:
            logger.warning(
                f"No existing state found for job {job_id} when setting success"
            )
            current_state = TaskStateInfo(
                job_id=job_id,
                state=TaskState.SUCCESS,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
                progress=[],
            )
        current_state.state = TaskState.SUCCESS
        current_state.result = result
        self.set_state(current_state)

    def set_failure(self, job_id: str, error: str) -> None:
        """Set job state to failed."""
        logger.info(f"Setting job {job_id} state to FAILURE: {error}")
        current_state = self.get_state(job_id)
        if not current_state:
            logger.warning(
                f"No existing state found for job {job_id} when setting failure"
            )
            current_state = TaskStateInfo(
                job_id=job_id,
                state=TaskState.FAILURE,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
                progress=[],
            )
        current_state.state = TaskState.FAILURE
        current_state.error = error
        self.set_state(current_state)

    def update_progress(
        self, job_id: str, stage: str, progress: float, message: str
    ) -> None:
        """Update job progress."""
        logger.debug(f"Updating progress for job {job_id}: {stage} - {progress}%")
        current_state = self.get_state(job_id)
        if not current_state:
            logger.warning(
                f"No existing state found for job {job_id} when updating progress"
            )
            current_state = TaskStateInfo(
                job_id=job_id,
                state=TaskState.STARTED,
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
                progress=[],
            )
        current_state.progress.append(
            TaskProgress(stage=stage, progress=progress, message=message)
        )
        self.set_state(current_state)

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


state_store = StateStore()
