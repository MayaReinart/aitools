from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from src.tasks.tasks import summarize_doc_task

router = APIRouter(prefix="/api", tags=["api"])


CONTENT_TYPES = [
    "application/json",
    "text/yaml",
    "application/x-yaml",
    "text/plain",
    "text/x-yaml",
]


class ExportFormat(str, Enum):
    HTML = "html"
    MARKDOWN = "markdown"
    DOCX = "docx"


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
    job_id = summarize_doc_task.delay(content.decode("utf-8"))

    return {"job_id": str(job_id)}


@router.get("/spec/{job_id}/summary", response_model=None)
async def get_summary(job_id: str) -> JSONResponse:
    """Retrieve a plain-English summary of the spec"""

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
    return JSONResponse(content={"status": result.status, "result": result.result})


@router.get("/spec/{job_id}/export", response_model=None)
async def export_summary(
    job_id: str,
    file_format: ExportFormat = ExportFormat.MARKDOWN,
) -> Response:
    """Export the summary in various formats"""
    # Ensure the results directory exists
    results_dir = Path("results") / job_id
    results_dir.mkdir(parents=True, exist_ok=True)

    if file_format == ExportFormat.HTML:
        return HTMLResponse("<h1>API Summary</h1>")

    if file_format == ExportFormat.MARKDOWN:
        file_path = results_dir / "summary.md"
        # Create an empty file if it doesn't exist (temporary)
        if not file_path.exists():
            file_path.write_text("# API Summary\n\nTo be implemented")
        return FileResponse(
            path=str(file_path),
            media_type="text/markdown; charset=utf-8",
            filename=f"api-summary-{job_id}.md",
        )

    if file_format == ExportFormat.DOCX:
        file_path = results_dir / "summary.docx"
        # Create an empty file if it doesn't exist (temporary)
        if not file_path.exists():
            file_path.write_bytes(b"")  # Empty DOCX for now
        return FileResponse(
            path=str(file_path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"api-summary-{job_id}.docx",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file format",
    )
