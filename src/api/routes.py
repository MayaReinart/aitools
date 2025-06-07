from typing import Any
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from loguru import logger

from src.api.models import validate_spec_file
from src.core.models import TaskState
from src.core.state import StateStore
from src.core.storage import ExportFormat, JobStorage, SpecFormat
from src.tasks.pipeline import create_processing_chain
from src.tasks.standalone import analyze_api_task

router = APIRouter(prefix="/api", tags=["api"])
state_store = StateStore()


def _detect_format(content_type: str | None) -> SpecFormat:
    """Detect file format from content type."""
    if content_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Please upload a JSON or YAML file.",
        )
    return SpecFormat.JSON if "json" in content_type else SpecFormat.YAML


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.post("/spec/upload")
async def upload_spec(
    file: UploadFile,
) -> dict[str, str]:
    """Upload an OpenAPI spec (YAML or JSON)"""
    # Validate and read file
    validate_spec_file(file)
    content = await file.read()
    spec_content = content.decode("utf-8")

    # Generate a unique job ID
    job_id = str(uuid4())

    # Save the uploaded spec
    storage = JobStorage(job_id)
    spec_format = _detect_format(file.content_type)
    storage.save_spec(spec_content, spec_format)

    # Start the processing chain
    chain = create_processing_chain(spec_content, job_id)
    chain.delay()

    return {"job_id": job_id}


@router.get("/spec/{job_id}/summary")
async def get_summary(job_id: str) -> JSONResponse:
    """Retrieve a plain-English summary of the spec"""
    storage = JobStorage(job_id)

    # Check task state first
    state = state_store.get_state(job_id)
    if not state:
        # Fall back to Celery state if not in our store
        result: AsyncResult[dict[str, Any]] = analyze_api_task.AsyncResult(job_id)
        if result.status == "PENDING":
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Job is still processing",
            )
        if result.status == "FAILURE":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Job failed",
            )

        # For success case, ensure we're returning a dict
        task_result = (
            result.result
            if isinstance(result.result, dict)
            else {"result": result.result}
        )
        return JSONResponse(content={"status": result.status, "result": task_result})

    # Return state from our store
    if state.state.value in ["PENDING", "STARTED", "PROGRESS"]:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": state.state.value,
                "progress": state.progress[-1].model_dump() if state.progress else None,
            },
        )

    if state.state == TaskState.FAILURE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=state.error or "Job failed",
        )

    # Save the summary if we haven't already
    if not storage.get_summary_path() and state.result:
        logger.info(f"Saving {job_id} summary")
        storage.save_summary(state.result)

    return JSONResponse(content={"status": state.state.value, "result": state.result})


@router.get("/spec/{job_id}/state")
async def get_job_state(job_id: str) -> JSONResponse:
    """Get the current state of a job.

    Args:
        job_id: Unique job identifier

    Returns:
        JSONResponse: Current job state and progress
    """
    # Check task state
    state = state_store.get_state(job_id)
    if not state:
        # Fall back to Celery state if not in our store
        result: AsyncResult[dict[str, Any]] = analyze_api_task.AsyncResult(job_id)
        if result.status == "PENDING":
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "status": "PENDING",
                    "message": "Job is queued for processing",
                },
            )
        if result.status == "FAILURE":
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "FAILURE",
                    "error": str(result.result) if result.result else "Unknown error",
                },
            )

        # For success case, ensure we're returning a dict
        task_result = (
            result.result
            if isinstance(result.result, dict)
            else {"result": result.result}
        )
        return JSONResponse(
            content={
                "status": result.status,
                "result": task_result,
            }
        )

    # Return state from our store
    response: dict[str, Any] = {
        "status": state.state.value,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }

    if state.progress:
        latest_progress = state.progress[-1]
        response["progress"] = {
            "stage": latest_progress.stage,
            "percentage": latest_progress.progress,
            "message": latest_progress.message,
            "timestamp": latest_progress.timestamp.isoformat(),
        }

    if state.state == TaskState.FAILURE:
        response["error"] = state.error if state.error else "Unknown error"

    if state.state == TaskState.SUCCESS and state.result:
        response["result"] = state.result

    return JSONResponse(content=response)


@router.get("/spec/{job_id}/export", response_model=None)
async def export_summary(
    job_id: str,
    file_format: ExportFormat = ExportFormat.MARKDOWN,
) -> Response:
    """Export the summary in various formats"""
    storage = JobStorage(job_id)

    # Check if the job exists
    if not storage.get_spec_path():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    path = storage.ensure_export_exists(file_format)

    if file_format == ExportFormat.HTML:
        return HTMLResponse(path.read_text())

    if file_format == ExportFormat.MARKDOWN:
        return FileResponse(
            path=str(path),
            media_type="text/markdown; charset=utf-8",
            filename=f"api-summary-{job_id}.md",
        )

    if file_format == ExportFormat.DOCX:
        return FileResponse(
            path=str(path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"api-summary-{job_id}.docx",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file format",
    )  # Unreachable but keeps mypy happy
