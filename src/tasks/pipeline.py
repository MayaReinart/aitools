"""Chain-based API processing pipeline."""

from typing import Any

from celery import Task  # type: ignore
from celery import chain as celery_chain  # type: ignore
from celery.canvas import Signature  # type: ignore
from loguru import logger

from src.core.celery_app import celery_app
from src.core.models import TaskState
from src.core.state import state_store
from src.core.storage import JobStorage
from src.services.llm import EndpointAnalysis, SpecAnalysis
from src.services.parser import ParsedSpec, parse_openapi_spec


class TaskError(Exception):
    """Base class for task errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TaskIDError(TaskError):
    """Error with task ID."""

    def __init__(self) -> None:
        super().__init__("Task ID is required")


class ParseError(TaskError):
    """Error parsing OpenAPI spec."""

    def __init__(self) -> None:
        super().__init__("Failed to parse OpenAPI spec")


class AnalysisError(TaskError):
    """Error analyzing OpenAPI spec."""

    def __init__(self) -> None:
        super().__init__("Failed to analyze OpenAPI spec")


class ExportError(TaskError):
    """Error exporting analysis results."""

    def __init__(self) -> None:
        super().__init__("Failed to export analysis results")


def update_progress(
    job_id: str,
    stage: str,
    progress: float,
    message: str | None = None,
) -> None:
    """Update job progress."""
    state_store.update_progress(job_id, stage, progress, message)
    # Update overall state to PROGRESS
    state = state_store.get_state(job_id)
    if state and state.state == TaskState.STARTED:
        state.state = TaskState.PROGRESS
        state_store.set_state(state)


@celery_app.task(bind=True, max_retries=3)
def parse_spec_task(self: Task, content: str, job_id: str) -> dict[str, Any]:
    """Parse and validate OpenAPI spec.

    Args:
        self: Task instance
        content: Raw OpenAPI spec content
        job_id: Job identifier

    Returns:
        dict: Dictionary containing parsed spec JSON and job_id
    """
    logger.info(f"[{job_id}] Starting parse_spec_task with task_id: {self.request.id}")

    if not self.request.id:
        raise TaskIDError()

    try:
        # Update task ID and ensure state is PROGRESS
        state_store.set_task_id(job_id, self.request.id)
        update_progress(
            job_id,
            stage="parsing",
            progress=0,
            message="Starting OpenAPI spec parsing",
        )
    except Exception as e:
        logger.error(f"[{job_id}] Error in parse_spec_task: {e!s}", exc_info=True)
        state_store.set_failure(job_id, str(e))
        raise self.retry(exc=e, countdown=5) from e

    try:
        parsed_spec = parse_openapi_spec(content)
        storage = JobStorage(job_id)

        # Save parsed spec using model_dump for consistent serialization
        spec_dict = parsed_spec.model_dump(mode="json")
        storage.save_parsed_spec(spec_dict)

        update_progress(
            job_id,
            stage="parsing",
            progress=100,
            message="Successfully parsed OpenAPI spec",
        )

    except Exception as e:
        logger.error(f"[{job_id}] Error in parse_spec_task: {e!s}", exc_info=True)
        state_store.set_failure(job_id, str(e))
        raise self.retry(exc=e, countdown=5) from e

    else:
        # Use the same serialization method for the result
        return {
            "spec": spec_dict,  # Already JSON-serializable
            "job_id": job_id,
            "task_id": self.request.id,
        }


@celery_app.task(bind=True, max_retries=3)
def analyze_spec_task(self: Task, parse_result: dict[str, Any]) -> dict[str, Any]:
    """Analyze spec using LLM.

    Args:
        self: Task instance
        parse_result: Result from parse task containing spec JSON and job_id

    Returns:
        dict: Analysis results with spec info, summary, and endpoints
    """
    job_id = parse_result["job_id"]
    logger.info(
        f"[{job_id}] Starting analyze_spec_task with task_id: {self.request.id}"
    )

    if not self.request.id:
        raise TaskIDError()

    try:
        # Update task ID and progress
        state_store.set_task_id(job_id, self.request.id)
        update_progress(
            job_id,
            stage="analysis",
            progress=0,
            message="Starting LLM analysis",
        )
    except Exception as e:
        logger.error(f"[{job_id}] Error in analyze_spec_task: {e!s}", exc_info=True)
        state_store.set_failure(job_id, str(e))
        raise self.retry(exc=e, countdown=5) from e

    try:
        # Convert dict back to ParsedSpec
        parsed_spec = ParsedSpec.model_validate(parse_result["spec"])

        # Mock analysis for now
        mock_analysis = SpecAnalysis(
            overview="Test API overview",
            endpoints=[
                EndpointAnalysis(
                    path="/test", method="GET", analysis="Test endpoint analysis"
                )
            ],
        )

        update_progress(
            job_id,
            stage="analysis",
            progress=100,
            message="Completed LLM analysis",
        )

        # Create complete result
        return {
            "spec_info": {
                "title": parsed_spec.title,
                "version": parsed_spec.version,
                "description": parsed_spec.description,
            },
            "summary": mock_analysis.model_dump(),
            "endpoints": [endpoint.model_dump() for endpoint in parsed_spec.endpoints],
            "job_id": job_id,
            "task_id": self.request.id,
            "previous_task": parse_result["task_id"],
        }

    except Exception as e:
        logger.error(f"[{job_id}] Error in analyze_spec_task: {e!s}", exc_info=True)
        state_store.set_failure(job_id, str(e))
        raise self.retry(exc=e, countdown=5) from e


@celery_app.task(bind=True, max_retries=3)
def generate_outputs_task(
    self: Task,
    analysis_result: dict[str, Any],
) -> dict[str, Any]:
    """Generate output files.

    Args:
        self: Task instance
        analysis_result: Analysis results from LLM containing job_id

    Returns:
        dict: Final results including file paths and analysis
    """
    job_id = analysis_result.get("job_id")
    if not job_id:
        raise ExportError()

    logger.info(
        f"[{job_id}] Starting generate_outputs_task with task_id: {self.request.id}"
    )

    if not self.request.id:
        raise TaskIDError()

    try:
        # Update task ID and progress
        state_store.set_task_id(job_id, self.request.id)
        update_progress(
            job_id,
            stage="export",
            progress=0,
            message="Starting export generation",
        )
    except Exception as e:
        logger.error(f"[{job_id}] Error in generate_outputs_task: {e!s}", exc_info=True)
        state_store.set_failure(job_id, str(e))
        raise self.retry(exc=e, countdown=5) from e

    try:
        storage = JobStorage(job_id)
        summary_path = storage.save_summary(analysis_result)
        log_path = storage.job_dir / "execution.log"
        logger.info(f"[{job_id}] Saving execution log to {log_path}")

        update_progress(
            job_id,
            stage="export",
            progress=100,
            message="Completed export generation",
        )

        result = {
            "summary_path": str(summary_path),
            "log_path": str(log_path),
            "analysis": analysis_result,
            "job_id": job_id,
            "task_id": self.request.id,
            "previous_task": analysis_result["task_id"],
        }
        state_store.set_success(job_id, result)

    except Exception as e:
        logger.error(f"[{job_id}] Error in generate_outputs_task: {e!s}", exc_info=True)
        state_store.set_failure(job_id, str(e))
        raise self.retry(exc=e, countdown=5) from e

    else:
        return result


def create_processing_chain(content: str, job_id: str) -> Signature:
    """Create task processing chain."""
    return celery_chain(
        parse_spec_task.s(content, job_id),
        analyze_spec_task.s(),
        generate_outputs_task.s(),
    )
