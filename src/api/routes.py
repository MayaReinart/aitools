"""API routes for the application."""

from typing import Any, ClassVar, Self
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from loguru import logger
from pydantic import BaseModel, ValidationError, field_validator

from src.api.exceptions import (
    InvalidFormatError,
    handle_upload_error,
)
from src.api.models import SummaryResponse, validate_spec_file
from src.core.celery_app import celery_app
from src.core.health import check_celery_worker, check_redis_connection
from src.core.models import TaskState
from src.core.state import state_store
from src.core.storage import ExportFormat, JobStorage, SpecFormat
from src.services.llm import embed_spec
from src.tasks.pipeline import create_summary_chain, query_spec_task
from src.tasks.standalone import verify_broker_connection

router = APIRouter(prefix="/api", tags=["api"])


def _detect_format(content_type: str | None) -> SpecFormat:
    """Detect file format from content type."""
    if content_type is None:
        raise InvalidFormatError()
    return SpecFormat.JSON if "json" in content_type else SpecFormat.YAML


@router.get("/health")
async def health_check() -> JSONResponse:
    """Check health of service dependencies."""
    redis_result = check_redis_connection()
    celery_result = check_celery_worker(celery_app)

    service_status = (
        "healthy"
        if redis_result.is_healthy and celery_result.is_healthy
        else "unhealthy"
    )

    response_content = {
        "status": service_status,
        "redis": {
            "healthy": redis_result.is_healthy,
            **redis_result.details,
        },
        "celery": {
            "healthy": celery_result.is_healthy,
            **celery_result.details,
        },
    }

    if not redis_result.is_healthy or not celery_result.is_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response_content,
        )

    return JSONResponse(content=response_content)


@router.post("/spec/upload")
async def upload_spec(file: UploadFile) -> dict[str, str]:
    """Upload an OpenAPI spec (YAML or JSON) and start processing pipeline."""
    job_id = None
    try:
        # Validate and read file
        validate_spec_file(file)
        content = await file.read()

        # Process spec
        spec_content = content.decode("utf-8")
        job_id = str(uuid4())

        # Save spec and get path
        storage = JobStorage(job_id)
        spec_path = storage.save_spec(spec_content, _detect_format(file.content_type))

        # Save spec embedding
        index = embed_spec(spec_path)
        storage.save_spec_embedding(index)

        # Create and verify chain
        chain = create_summary_chain(str(spec_path), job_id)
        verify_broker_connection(chain)

        # Start task and store ID
        result = chain.apply_async()
        state_store.set_task_id(job_id, result.id)

    except (InvalidFormatError, HTTPException) as e:
        # Re-raise HTTP exceptions directly
        if isinstance(e, HTTPException):
            raise
        # Convert InvalidFormatError to HTTPException
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise handle_upload_error(e, job_id) from e

    else:
        # Log and return
        logger.info(f"[{job_id}] Started task chain: {result.id}")
        return {"job_id": job_id}


@router.get("/spec/{job_id}/summary")
async def get_summary(job_id: str) -> JSONResponse:
    """Retrieve a plain-English summary of the spec"""
    storage = JobStorage(job_id)

    # Check task state first
    state = state_store.get_state(job_id)

    logger.debug(f"[{job_id}] State: {state.model_dump() if state else None}")

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if state.state == TaskState.FAILURE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=state.error or "Job failed",
        )

    # Not failure
    response = SummaryResponse(
        status=state.state.value,
        current_job_name=state.progress[-1].stage if state.progress else None,
        current_job_progress=state.progress[-1].progress if state.progress else None,
    )

    # Return state from our store
    if state.state != TaskState.SUCCESS:
        logger.debug(f"[{job_id}] Returning 202 - State is {state.state}")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=response.model_dump(),
        )

    # Success
    # Save the summary if we haven't already
    if not storage.get_summary_path() and state.result:
        logger.info(f"Saving {job_id} summary")
        storage.save_summary(state.result)

    response.result = state.result
    logger.debug(f"[{job_id}] Returning 200 - State is {state.state}")
    return JSONResponse(content=response.model_dump())


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
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

    # Check if the job exists and has a summary
    if not storage.get_summary_path():
        # Check if job exists but summary is not ready
        if storage.get_spec_path():
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Summary is not ready yet",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Get the export content and media type
    content, media_type = storage.get_export_content(file_format)

    # Return appropriate response based on content type
    if file_format == ExportFormat.HTML:
        return HTMLResponse(content=content)
    if file_format == ExportFormat.DOCX:
        return FileResponse(
            path=storage.ensure_export_exists(file_format),
            media_type=media_type,
            filename=f"api_summary.{file_format}",
        )
    # MARKDOWN
    return Response(content=content, media_type=media_type)


class SpecQuery(BaseModel):
    """Query model for spec analysis."""

    QUERY_MAX_LENGTH: ClassVar[int] = 1000

    query: str

    @field_validator("query")
    @classmethod
    def validate_query(cls: type[Self], v: str) -> str:
        if not v.strip() or len(v) > cls.QUERY_MAX_LENGTH:
            raise ValidationError
        return v.strip()


@router.post("/spec/{job_id}/query")
async def query_spec(
    job_id: str,
    query: SpecQuery,
) -> JSONResponse:
    """Query the uploaded spec with a natural language question."""

    # Check job state
    state = state_store.get_state(job_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    if state.state == TaskState.FAILURE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job failed, cannot query spec",
        )
    if state.state != TaskState.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not complete, cannot query spec",
        )

    try:
        result = query_spec_task.delay(job_id=job_id, query=query.query)

        logger.info(f"[{job_id}] Started query task: {result.id}")

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "job_id": job_id,
                "status": "processing",
                "message": "Query is being processed",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating query: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {e!s}",
        ) from e


@router.get("/spec/{job_id}/query")
async def get_query_result(job_id: str) -> JSONResponse:
    """Get the result of a spec query."""
    # Check if the original job exists
    if not JobStorage(job_id).get_spec_path():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Get query state
    state = state_store.get_state(job_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )

    if state.state == TaskState.FAILURE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=state.error or "Query failed",
        )

    if state.state != TaskState.SUCCESS:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": state.state.value,
                "current_job_name": state.progress[-1].stage
                if state.progress
                else None,
                "current_job_progress": state.progress[-1].progress
                if state.progress
                else None,
            },
        )

    # Success
    return JSONResponse(content={"answer": state.result})
