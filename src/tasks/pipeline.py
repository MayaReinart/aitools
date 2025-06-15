"""Chain-based API processing pipeline."""

import json
from pathlib import Path
from typing import Any

from celery import Task  # type: ignore
from celery.canvas import chain as celery_chain  # type: ignore
from loguru import logger

from src.core.celery_app import celery_app
from src.core.config import settings
from src.core.models import TaskState, TaskStatus
from src.core.state import state_store
from src.core.storage import JobStorage
from src.core.utils import handle_task_errors, setup_task_config, temporary_file
from src.services.llm import EndpointAnalysis, SpecAnalysis, get_llm_spec_analysis
from src.services.parser import ParsedSpec, parse_spec


class TaskError(Exception):
    """Base class for task errors."""


class TaskIDError(TaskError):
    """Raised when task ID is missing."""


class AnalysisError(TaskError):
    """Raised when analysis fails."""


def update_progress(
    job_id: str,
    stage: str,
    progress: int,
    message: str | None = None,
) -> None:
    """Update job progress.

    Args:
        job_id: Job identifier
        stage: Current processing stage
        progress: Progress percentage (0-100)
        message: Optional status message
    """
    state = TaskStatus(
        job_id=job_id,
        state=TaskState.PROGRESS,
    )
    state.update_progress(stage, progress, message)
    state_store.set_state(state)


@celery_app.task(**setup_task_config())
@handle_task_errors()
def parse_spec_task(self: Task, job_id: str, spec_path: str) -> dict[str, Any]:
    """Parse and analyze an OpenAPI specification.

    Args:
        job_id: The job ID
        spec_path: Path to the specification file or the spec content itself

    Returns:
        dict: Analysis results
    """
    logger.info(f"[{job_id}] Starting parse_spec_task with task_id: {self.request.id}")

    try:
        # Check if spec_path is actually a file path or spec content
        if Path(spec_path).exists():
            spec = parse_spec(Path(spec_path))
        else:
            with temporary_file(spec_path) as temp_path:
                spec = parse_spec(temp_path)

        # Get LLM analysis
        analysis = get_llm_spec_analysis(spec)

        # Save results
        results_path = settings.job_data_path / f"{job_id}_analysis.json"
        with results_path.open("w") as f:
            json.dump(analysis.model_dump(), f, indent=2)

        logger.info(f"[{job_id}] Successfully completed parse_spec_task")
        return {
            "status": "success",
            "job_id": job_id,
            "spec": spec.model_dump(),
            "task_id": self.request.id,
        }
    except Exception as e:
        logger.error(f"[{job_id}] Error in parse_spec_task: {e}")
        state_store.set_failure(job_id, str(e))
        raise


def _raise_task_error(job_id: str, error_msg: str) -> None:
    """Raise a task error with the given error message.

    Args:
        job_id: The job ID
        error_msg: The error message

    Raises:
        TaskError: The task error
    """
    logger.error(f"[{job_id}] {error_msg}")
    state_store.set_failure(job_id, error_msg)
    raise TaskError(error_msg)


@celery_app.task(**setup_task_config())
@handle_task_errors()
def analyze_spec_task(self: Task, parse_result: dict[str, Any]) -> dict[str, Any]:
    """Analyze spec using LLM.

    Args:
        parse_result: Results from parse_spec_task

    Returns:
        dict: Analysis results with spec info, summary, and endpoints
    """
    job_id = parse_result.get("job_id")
    if not job_id:
        raise TaskIDError()

    task_id = self.request.id
    if not task_id:
        raise TaskIDError()

    logger.info(f"[{job_id}] Starting analyze_spec_task with task_id: {task_id}")

    try:
        # Update task ID and ensure state is PROGRESS
        state_store.set_task_id(job_id, task_id)
        update_progress(
            job_id,
            stage="analysis",
            progress=0,
            message="Starting spec analysis",
        )
    except Exception as e:
        logger.error(f"[{job_id}] Error in analyze_spec_task: {e}")
        state_store.set_failure(job_id, str(e))
        raise

    try:
        if parse_result.get("status") == "error":
            error_msg = parse_result.get("error", "Unknown error in previous task")
            _raise_task_error(job_id, error_msg)

        spec_data = parse_result.get("spec")
        if not spec_data:
            _raise_task_error(job_id, "Missing spec data from previous task")

        # Convert dict back to ParsedSpec
        parsed_spec = ParsedSpec.model_validate(spec_data)

        # Mock analysis for now
        mock_analysis = SpecAnalysis(
            overview="API Overview",
            endpoints=[
                EndpointAnalysis(
                    path=endpoint.path,
                    method=endpoint.method,
                    analysis=f"Analysis for {endpoint.method} {endpoint.path}",
                )
                for endpoint in parsed_spec.endpoints
            ],
        )

        update_progress(
            job_id,
            stage="analysis",
            progress=100,
            message="Analysis complete",
        )

        return {
            "analysis": mock_analysis.model_dump(),
            "endpoints": [endpoint.model_dump() for endpoint in parsed_spec.endpoints],
            "job_id": job_id,
            "task_id": task_id,
            "previous_task": parse_result.get("task_id"),
        }

    except Exception as e:
        logger.error(f"[{job_id}] Error in analyze_spec_task: {e}")
        state_store.set_failure(job_id, str(e))
        raise


@celery_app.task(**setup_task_config())
@handle_task_errors()
def generate_outputs_task(
    self: Task,
    analysis_result: dict[str, Any],
) -> dict[str, Any]:
    """Generate output files from analysis.

    Args:
        analysis_result: Results from analyze_spec_task

    Returns:
        dict: Generated output files and metadata
    """
    job_id = analysis_result.get("job_id")
    if not job_id:
        raise TaskIDError()

    task_id = self.request.id
    if not task_id:
        raise TaskIDError()

    logger.info(f"[{job_id}] Starting generate_outputs_task with task_id: {task_id}")

    try:
        # Update task ID and ensure state is PROGRESS
        state_store.set_task_id(job_id, task_id)
        update_progress(
            job_id,
            stage="generation",
            progress=0,
            message="Starting output generation",
        )
    except Exception as e:
        logger.error(f"[{job_id}] Error in generate_outputs_task: {e}")
        state_store.set_failure(job_id, str(e))
        raise

    try:
        storage = JobStorage(job_id)

        # Generate mock outputs for now
        outputs = {
            "overview.md": "# API Overview\n\nThis is a mock overview.",
            "endpoints.md": "# Endpoints\n\nThis is a mock endpoints document.",
        }

        # Save outputs
        for filename, content in outputs.items():
            storage.save_output(filename, content)

        update_progress(
            job_id,
            stage="generation",
            progress=100,
            message="Output generation complete",
        )

        return {
            "outputs": list(outputs.keys()),
            "job_id": job_id,
            "task_id": task_id,
            "previous_task": analysis_result.get("task_id"),
        }
    except Exception as e:
        logger.error(f"[{job_id}] Error in generate_outputs_task: {e}")
        state_store.set_failure(job_id, str(e))
        raise


def create_processing_chain(content: str, job_id: str) -> celery_chain:
    """Create a chain of tasks for processing an API specification.

    Args:
        content: The specification content
        job_id: The job ID

    Returns:
        A chain of tasks to process the specification
    """
    return celery_chain(
        parse_spec_task.s(job_id=job_id, spec_path=content),
        analyze_spec_task.s(),
        generate_outputs_task.s(),
    )
