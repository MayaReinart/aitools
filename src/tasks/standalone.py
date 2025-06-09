"""Standalone API processing tasks."""

from typing import Any

from celery.signals import task_failure, task_success

from src.core.state import state_store


@task_success.connect
def handle_success(
    _sender: object = None,
    result: dict[str, Any] | None = None,
    **_kwargs: dict[str, Any],
) -> None:
    """Handle successful task completion."""
    if isinstance(result, dict) and "job_id" in result:
        state_store.set_success(result["job_id"], result)


@task_failure.connect
def handle_failure(
    _sender: object = None,
    args: tuple[str, ...] | None = None,
    exception: Exception | None = None,
    **_kwargs: dict[str, Any],
) -> None:
    """Handle task failure."""
    if args and args[0]:  # job_id is first argument
        state_store.set_failure(args[0], str(exception))
