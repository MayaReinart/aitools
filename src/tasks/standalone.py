"""Standalone API processing tasks."""

import json
from typing import Any

from celery import Task, shared_task
from celery.signals import task_failure, task_success
from loguru import logger

from src.core.state import StateStore
from src.core.storage import JobStorage
from src.services.llm import get_llm_spec_analysis
from src.services.parser import ParsedSpec, parse_openapi_spec

state_store = StateStore()


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


def update_progress(job_id: str, stage: str, progress: float, message: str) -> None:
    """Update task progress."""
    logger.info(f"[{job_id}] {stage} - {progress}%: {message}")
    state_store.update_progress(job_id, stage, progress, message)


@shared_task(bind=True, max_retries=3)
def analyze_api_task(
    self: Task,
    content: str,
    job_id: str,
    storage: JobStorage | None = None,
) -> dict[str, Any]:
    """Single-task API analysis with caching support.

    Args:
        self: The Celery task instance
        content: Raw OpenAPI spec content
        job_id: Unique identifier for the job
        storage: Optional storage instance (used in testing)

    Returns:
        dict: Structured summary of the API

    Raises:
        Exception: If parsing or summarization fails
    """
    try:
        if storage is None:
            storage = JobStorage(job_id)

        # Mark task as started
        state_store.set_started(job_id)
        update_progress(job_id, "parsing", 0, "Starting API analysis")
        result = _process_spec(content, storage, job_id)
    except Exception as e:
        logger.error(f"Error processing spec: {e}")
        self.retry(exc=e, countdown=5, max_retries=3)
        raise
    else:
        result["job_id"] = job_id  # Add job_id for success handler
        return result


def _process_spec(content: str, storage: JobStorage, job_id: str) -> dict[str, Any]:
    """Process an OpenAPI spec and generate summary.

    Args:
        content: Raw OpenAPI spec content
        storage: Storage instance for caching
        job_id: Unique identifier for the job

    Returns:
        dict: Analysis results

    Raises:
        Exception: If parsing or summarization fails
    """
    # Stage 1: Load or parse spec
    update_progress(job_id, "parsing", 25, "Loading OpenAPI specification")

    parsed_spec = _load_cached_spec(storage)
    if not parsed_spec:
        update_progress(job_id, "parsing", 50, "Parsing OpenAPI specification")
        parsed_spec = _parse_and_cache_spec(content, storage)

    update_progress(job_id, "parsing", 75, "OpenAPI specification parsed successfully")

    # Stage 2: Generate summary
    update_progress(job_id, "analysis", 0, "Starting LLM analysis")
    summary = get_llm_spec_analysis(parsed_spec)
    update_progress(job_id, "analysis", 100, "Completed LLM analysis")

    return {
        "spec_info": {
            "title": parsed_spec.title,
            "version": parsed_spec.version,
            "description": parsed_spec.description,
        },
        "summary": summary,
        "endpoints": parsed_spec.endpoints,
    }


def _load_cached_spec(storage: JobStorage) -> ParsedSpec | None:
    """Attempt to load cached spec.

    Args:
        storage: Storage instance to load from

    Returns:
        Parsed spec if found and valid, None otherwise
    """
    parsed_spec_path = storage.get_parsed_spec_path()
    if not parsed_spec_path:
        return None

    try:
        logger.info("Found cached parsed spec, attempting to load")
        parsed_spec_content = parsed_spec_path.read_text()
        parsed_spec = ParsedSpec.model_validate_json(parsed_spec_content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to load cached parsed spec: {e}")
        return None
    else:
        return parsed_spec


def _parse_and_cache_spec(content: str, storage: JobStorage) -> ParsedSpec:
    """Parse spec and cache the result.

    Args:
        content: Raw OpenAPI spec content
        storage: Storage instance for caching

    Returns:
        Parsed spec
    """
    logger.info("Parsing OpenAPI spec")
    parsed_spec = parse_openapi_spec(content)
    storage.save_parsed_spec(parsed_spec.model_dump())
    return parsed_spec
