from typing import cast

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from src.core.storage import ExportFormat, JobStorage, SpecFormat
from src.tasks.tasks import summarize_doc_task

router = APIRouter(prefix="/api", tags=["api"])


CONTENT_TYPES = [
    "application/json",
    "text/yaml",
    "application/x-yaml",
    "text/plain",
    "text/x-yaml",
]


def _detect_format(content_type: str) -> SpecFormat:
    """Detect file format from content type."""
    return SpecFormat.JSON if "json" in content_type else SpecFormat.YAML


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.post("/spec/upload")
async def upload_spec(
    file: UploadFile,
) -> dict[str, str]:
    """Upload an OpenAPI spec (YAML or JSON)"""
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )
    if file.content_type not in CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Please upload a JSON or YAML file.",
        )

    content = await file.read()
    spec_content = content.decode("utf-8")

    # Start the processing task
    job_id = str(summarize_doc_task.delay(spec_content))

    # Save the uploaded spec
    storage = JobStorage(job_id)
    format_ = _detect_format(file.content_type)
    storage.save_spec(spec_content, format_)

    return {"job_id": job_id}


@router.get("/spec/{job_id}/summary", response_model=None)
async def get_summary(job_id: str) -> JSONResponse:
    """Retrieve a plain-English summary of the spec"""
    storage = JobStorage(job_id)

    result = summarize_doc_task.AsyncResult(job_id)
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

    # Save the summary if we haven't already
    if result.status == "SUCCESS" and not storage.get_summary_path():
        storage.save_summary(cast(dict, result.result))

    return JSONResponse(content={"status": result.status, "result": result.result})


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

    if file_format == ExportFormat.HTML:
        path = storage.ensure_export_exists(ExportFormat.HTML)
        return HTMLResponse(path.read_text())

    if file_format == ExportFormat.MARKDOWN:
        path = storage.ensure_export_exists(ExportFormat.MARKDOWN)
        return FileResponse(
            path=str(path),
            media_type="text/markdown; charset=utf-8",
            filename=f"api-summary-{job_id}.md",
        )

    if file_format == ExportFormat.DOCX:
        path = storage.ensure_export_exists(ExportFormat.DOCX)
        return FileResponse(
            path=str(path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"api-summary-{job_id}.docx",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file format",
    )
