"""Common utility functions and patterns."""

import contextlib
from collections.abc import Callable, Generator
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from celery import Task
from loguru import logger
from pydantic import BaseModel

from src.core.config import settings

T = TypeVar("T")


class TaskError(Exception):
    """Base class for task errors."""

    MISSING_JOB_ID = "Job ID not found in arguments"


def handle_task_errors(
    countdown: int = 5,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for handling common task errors and retries.

    Args:
        countdown: Delay between retries in seconds

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(self: Task, *args: tuple[Any, ...], **kwargs: dict[str, Any]) -> T:
            job_id = kwargs.get("job_id") or (args[0] if args else None)
            if not job_id:
                raise TaskError(TaskError.MISSING_JOB_ID)

            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"[{job_id}] Error in {func.__name__}: {e}")
                if settings.ENV.lower() != "dev":
                    raise self.retry(exc=e, countdown=countdown) from e
                raise

        return wrapper

    return decorator


@contextlib.contextmanager
def temporary_file(content: str, suffix: str = ".yaml") -> Generator[Path, None, None]:
    """Context manager for handling temporary files.

    Args:
        content: Content to write to the file
        suffix: File suffix

    Yields:
        Path to the temporary file
    """
    temp_dir = Path(settings.job_data_path) / "temp"
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"temp_{hash(content)}{suffix}"

    try:
        temp_path.write_text(content)
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            temp_dir.rmdir()


def setup_task_config() -> dict[str, Any]:
    """Get task configuration based on environment.

    Returns:
        Task configuration dictionary
    """
    config: dict[str, Any] = {"bind": True}
    if settings.ENV.lower() != "dev":
        config["max_retries"] = 3
    return config


def pydantic_task(
    model_cls: type[BaseModel],
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Decorator to (de)serialize Pydantic models for Celery tasks."""

    def decorator(fn: Callable[..., object]) -> Callable[..., object]:
        def wrapper(self: object, *args: object, **kwargs: object) -> object:
            # Deserialize first arg if it's a dict and model_cls is provided
            if args and isinstance(args[0], dict):
                args = (model_cls.model_validate(args[0]),) + args[1:]
            result = fn(self, *args, **kwargs)
            # Serialize output if it's a model
            if isinstance(result, BaseModel):
                return result.model_dump()
            return result

        return wrapper

    return decorator
