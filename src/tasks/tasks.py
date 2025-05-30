"""Background tasks for API processing."""

from celery import Task
from loguru import logger

from celery_worker import celery_app
from src.services.llm import analyze_spec
from src.services.parser import parse_openapi_spec


@celery_app.task(bind=True)
def summarize_doc_task(self: Task, content: str) -> dict:
    """
    Parse an OpenAPI spec and generate a summary.

    Args:
        content: Raw OpenAPI spec content

    Returns:
        dict: Structured summary of the API

    Raises:
        Exception: If parsing or summarization fails
    """
    try:
        # Parse and validate the spec
        logger.info("Parsing OpenAPI spec")
        parsed_spec = parse_openapi_spec(content)

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
