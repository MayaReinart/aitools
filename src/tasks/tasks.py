"""Background tasks for API processing."""

import json

from celery import Task
from loguru import logger

from celery_worker import celery_app
from src.core.storage import JobStorage
from src.services.llm import analyze_spec
from src.services.parser import parse_openapi_spec


@celery_app.task(bind=True)
def summarize_doc_task(
    self: Task, content: str, job_id: str, storage: JobStorage | None = None
) -> dict:
    """
    Parse an OpenAPI spec and generate a summary.

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
        # Use provided storage or create new one
        storage = storage or JobStorage(job_id)
        parsed_spec = None

        # Check if we have a cached parsed spec
        parsed_spec_path = storage.get_parsed_spec_path()
        if parsed_spec_path:
            try:
                logger.info("Found cached parsed spec, attempting to load")
                parsed_spec_content = parsed_spec_path.read_text()
                parsed_spec = json.loads(parsed_spec_content)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to load cached parsed spec: {e}")

        if not parsed_spec:
            # Parse and validate the spec
            logger.info("Parsing OpenAPI spec")
            parsed_spec = parse_openapi_spec(content)
            # Cache the parsed spec
            storage.save_parsed_spec(parsed_spec.model_dump())

        # Generate summaries
        logger.info("Generating API summary")
        summary = analyze_spec(parsed_spec)
    except Exception as e:
        logger.error(f"Error processing spec: {e}")
        self.retry(exc=e, countdown=5, max_retries=3)
        raise  # This will never be reached, but makes mypy happy
    else:
        return {
            "spec_info": {
                "title": parsed_spec.title,
                "version": parsed_spec.version,
                "description": parsed_spec.description,
            },
            "summary": summary,
            "endpoints": parsed_spec.endpoints,
        }
