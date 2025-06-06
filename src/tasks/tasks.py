"""Background tasks for API processing."""

import json
from typing import Any

from celery import Task
from loguru import logger

from celery_worker import celery_app
from src.core.state import StateStore
from src.core.storage import JobStorage
from src.services.llm import get_llm_spec_analysis
from src.services.parser import ParsedSpec, parse_openapi_spec

state_store = StateStore()


@celery_app.task(bind=True)
def summarize_doc_task(
    self: Task, content: str, job_id: str, storage: JobStorage | None = None
) -> dict[str, Any]:
    """Parse an OpenAPI spec and generate a summary.

    Args:
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

        return _process_spec(content, storage, job_id)
    except Exception as e:
        logger.error(f"Error processing spec: {e}")
        state_store.set_retry(job_id, str(e))
        self.retry(exc=e, countdown=5, max_retries=3)
        raise  # This will never be reached, but makes mypy happy


def _process_spec(content: str, storage: JobStorage, job_id: str) -> dict[str, Any]:
    """Process an OpenAPI spec and generate summary.

    Args:
        content: Raw OpenAPI spec content
        storage: Storage instance for caching
        job_id: Unique identifier for the job

    Returns:
        Tuple of (parsed spec, summary)
    """
    try:
        # Stage 1: Load or parse spec
        state_store.update_progress(
            job_id,
            stage="parsing",
            progress=0,
            message="Loading OpenAPI specification",
        )

        parsed_spec = _load_cached_spec(storage)
        if not parsed_spec:
            state_store.update_progress(
                job_id,
                stage="parsing",
                progress=25,
                message="Parsing OpenAPI specification",
            )
            parsed_spec = _parse_and_cache_spec(content, storage)

        state_store.update_progress(
            job_id,
            stage="parsing",
            progress=50,
            message="OpenAPI specification parsed successfully",
        )

        # Stage 2: Generate summary
        state_store.update_progress(
            job_id,
            stage="analysis",
            progress=75,
            message="Analyzing API with LLM",
        )

        summary = get_llm_spec_analysis(parsed_spec)

        result = {
            "spec_info": {
                "title": parsed_spec.title,
                "version": parsed_spec.version,
                "description": parsed_spec.description,
            },
            "summary": summary,
            "endpoints": parsed_spec.endpoints,
        }

        state_store.set_success(job_id, result)
    except Exception as e:
        state_store.set_failure(job_id, str(e))
        raise
    else:
        return result


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
        return ParsedSpec.model_validate_json(parsed_spec_content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to load cached parsed spec: {e}")
        return None


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
