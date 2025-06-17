"""Chain-based API processing pipeline."""

from pathlib import Path
from typing import Any

from celery import Task  # type: ignore
from celery.canvas import chain as celery_chain  # type: ignore
from loguru import logger
from pydantic import BaseModel

from src.core.celery_app import celery_app
from src.core.models import TaskState, TaskStatus
from src.core.state import state_store
from src.core.storage import JobStorage
from src.core.utils import (
    handle_task_errors,
    pydantic_task,
    setup_task_config,
)
from src.services.llm import EndpointAnalysis, SpecAnalysis, get_llm_spec_analysis
from src.services.models import ParsedEndpoint, ParsedSpec
from src.services.parser import parse_spec


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


class ParseSpecResult(BaseModel):
    """Result of parse_spec_task."""

    status: str
    job_id: str
    spec: ParsedSpec  # Change from dict[str, Any] to ParsedSpec
    task_id: str | None = None


class AnalysisResult(BaseModel):
    """Result of analyze_spec_task."""

    analysis: SpecAnalysis
    endpoints: list[
        ParsedEndpoint
    ]  # Change from list[dict[str, Any]] to list[ParsedEndpoint]
    job_id: str
    task_id: str
    previous_task: str | None = None


class OutputResult(BaseModel):
    """Result of generate_outputs_task."""

    outputs: list[str]
    job_id: str
    task_id: str
    previous_task: str | None = None
    analysis: dict[str, Any] | None = None


@celery_app.task(**setup_task_config())
@handle_task_errors()
@pydantic_task(ParseSpecResult)
def parse_spec_task(self: Task, job_id: str, spec_path: str) -> ParseSpecResult:
    """Parse and analyze an OpenAPI specification.

    Args:
        job_id: The job ID
        spec_path: Path to the specification file

    Returns:
        ParseSpecResult: Analysis results
    """
    logger.info(f"[{job_id}] Starting parse_spec_task with task_id: {self.request.id}")

    try:
        spec = parse_spec(Path(spec_path))
        logger.info(f"[{job_id}] Successfully completed parse_spec_task")
        return ParseSpecResult(
            status="success",
            job_id=job_id,
            spec=spec,
            task_id=self.request.id,
        )
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
@pydantic_task(ParseSpecResult)
def analyze_spec_task(self: Task, parse_result: ParseSpecResult) -> AnalysisResult:
    """Analyze spec using LLM.

    Args:
        parse_result: Results from parse_spec_task

    Returns:
        AnalysisResult: Analysis results with spec info, summary, and endpoints
    """
    job_id = parse_result.job_id
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
        if parse_result.status == "error":
            error_msg = "Unknown error in previous task"
            _raise_task_error(job_id, error_msg)

        parsed_spec: ParsedSpec = parse_result.spec

        # Create endpoint analyses for each endpoint
        endpoint_analyses = []
        for endpoint in parsed_spec.endpoints:
            analysis = EndpointAnalysis(
                path=endpoint.path,
                method=endpoint.method,
                # Mock analysis for now
                analysis=f"Analysis for {endpoint.method} {endpoint.path}",
            )
            endpoint_analyses.append(analysis)

        # Create the spec analysis
        spec_analysis = get_llm_spec_analysis(parsed_spec)

        update_progress(
            job_id,
            stage="analysis",
            progress=100,
            message="Analysis complete",
        )

        return AnalysisResult(
            analysis=spec_analysis,
            endpoints=parsed_spec.endpoints,
            job_id=job_id,
            task_id=task_id,
            previous_task=parse_result.task_id,
        )

    except Exception as e:
        logger.error(f"[{job_id}] Error in analyze_spec_task: {e}")
        state_store.set_failure(job_id, str(e))
        raise


@celery_app.task(**setup_task_config())
@handle_task_errors()
@pydantic_task(AnalysisResult)
def generate_outputs_task(
    self: Task,
    analysis_result: AnalysisResult,
) -> OutputResult:
    """Generate output files from analysis.

    Args:
        analysis_result: Results from analyze_spec_task

    Returns:
        OutputResult: Generated output files and metadata
    """
    job_id = analysis_result.job_id
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

        spec_analysis: SpecAnalysis = analysis_result.analysis

        outputs = {
            "overview.md": spec_analysis.overview,
            "endpoints.md": spec_analysis.endpoints_analysis,
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

        # Return result that will be handled by the signal handler
        return OutputResult(
            outputs=list(outputs.keys()),
            job_id=job_id,
            task_id=task_id,
            previous_task=analysis_result.previous_task,
            analysis={
                "spec_info": {
                    "title": spec_analysis.overview.split(" for ")[-1],
                    "description": spec_analysis.overview,
                },
                "summary": {
                    "overview": spec_analysis.overview,
                },
                "endpoints": [
                    {
                        "path": endpoint.path,
                        "method": endpoint.method,
                        "analysis": endpoint.analysis,
                    }
                    for endpoint in spec_analysis.endpoints
                ],
            },
        )
    except Exception as e:
        logger.error(f"[{job_id}] Error in generate_outputs_task: {e}")
        state_store.set_failure(job_id, str(e))
        raise


def create_processing_chain(spec_path: str, job_id: str) -> celery_chain:
    """Create a chain of tasks for processing an API specification.

    Args:
        spec_path: Path to the saved specification file
        job_id: The job ID

    Returns:
        A chain of tasks to process the specification
    """
    return celery_chain(
        parse_spec_task.s(job_id=job_id, spec_path=spec_path),
        analyze_spec_task.s(),
        generate_outputs_task.s(),
    )
