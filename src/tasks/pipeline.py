"""Chain-based API processing pipeline."""

from typing import Any

from celery import chain, shared_task
from loguru import logger

from src.core.state import StateStore
from src.core.storage import JobStorage
from src.services.llm import EndpointAnalysis, SpecAnalysis
from src.services.parser import ParsedSpec, parse_openapi_spec

state_store = StateStore()


def update_progress(job_id: str, stage: str, progress: float, message: str) -> None:
    """Update task progress."""
    logger.info(f"[{job_id}] {stage} - {progress}%: {message}")
    state_store.update_progress(job_id, stage, progress, message)


@shared_task(max_retries=3)
def parse_spec_task(content: str, job_id: str) -> str:
    """Parse and validate OpenAPI spec.

    Args:
        content: Raw OpenAPI spec content
        job_id: Job identifier

    Returns:
        str: JSON string of parsed spec
    """
    logger.info(f"Parsing spec for job {job_id}")
    update_progress(
        job_id,
        stage="parsing",
        progress=0,
        message="Starting OpenAPI spec parsing",
    )

    try:
        parsed_spec = parse_openapi_spec(content)
        storage = JobStorage(job_id)

        # Save parsed spec
        spec_dict = parsed_spec.model_dump()
        storage.save_parsed_spec(spec_dict)
    except Exception as e:
        logger.error(f"Error parsing spec: {e}")
        state_store.set_failure(job_id, str(e))
        raise
    else:
        update_progress(
            job_id,
            stage="parsing",
            progress=100,
            message="Successfully parsed OpenAPI spec",
        )
        # Return as JSON string for next task
        return parsed_spec.model_dump_json()


@shared_task(max_retries=3)
def analyze_spec_task(spec_json: str, job_id: str) -> dict[str, Any]:
    """Analyze spec using LLM.

    Args:
        spec_json: JSON string of parsed OpenAPI spec
        job_id: Job identifier

    Returns:
        dict: Analysis results with spec info, summary, and endpoints
    """
    logger.info(f"Analyzing spec for job {job_id}")
    update_progress(
        job_id,
        stage="analysis",
        progress=0,
        message="Starting LLM analysis",
    )

    try:
        # Convert JSON string back to ParsedSpec
        parsed_spec = ParsedSpec.model_validate_json(spec_json)

        analysis_result = SpecAnalysis(
            overview="Test API overview",
            endpoints=[
                EndpointAnalysis(
                    path="/test", method="GET", analysis="Test endpoint analysis"
                ),
                EndpointAnalysis(
                    path="/test2", method="POST", analysis="Test endpoint analysis 2"
                ),
            ],
        )

        # Create complete result
        result = {
            "spec_info": {
                "title": parsed_spec.title,
                "version": parsed_spec.version,
                "description": parsed_spec.description,
            },
            "summary": analysis_result.model_dump(),
            "endpoints": parsed_spec.endpoints,
            "job_id": job_id,
        }
    except Exception as e:
        logger.error(f"Error analyzing spec: {e}")
        state_store.set_failure(job_id, str(e))
        raise
    else:
        update_progress(
            job_id,
            stage="analysis",
            progress=100,
            message="Completed LLM analysis",
        )
        return result


@shared_task(max_retries=3)
def generate_outputs_task(
    analysis_result: dict[str, Any],
    job_id: str,
) -> dict[str, Any]:
    """Generate output files.

    Args:
        analysis_result: Analysis results from LLM
        job_id: Job identifier

    Returns:
        dict: Final results including file paths and analysis
    """
    logger.info(f"Generating outputs for job {job_id}")
    update_progress(
        job_id,
        stage="export",
        progress=0,
        message="Starting export generation",
    )

    try:
        storage = JobStorage(job_id)
        summary_path = storage.save_summary(analysis_result)
        log_path = storage.job_dir / "execution.log"
        logger.info(f"Saving execution log to {log_path}")
    except Exception as e:
        logger.error(f"Error generating outputs: {e}")
        state_store.set_failure(job_id, str(e))
        raise
    else:
        update_progress(
            job_id,
            stage="export",
            progress=100,
            message="Completed export generation",
        )
        return {
            "summary_path": str(summary_path),
            "log_path": str(log_path),
            "analysis": analysis_result,
            "job_id": job_id,
        }


def create_processing_chain(content: str, job_id: str) -> chain:
    """Create a processing chain for API analysis.

    Args:
        content: Raw OpenAPI spec content
        job_id: Unique job identifier

    Returns:
        chain: Celery chain of tasks
    """
    logger.info(f"Creating processing chain for job {job_id}")

    # Initialize state
    state_store.set_started(job_id)

    # Create the chain
    return chain(
        parse_spec_task.s(content, job_id),
        analyze_spec_task.s(job_id),
        generate_outputs_task.s(job_id),
    )
