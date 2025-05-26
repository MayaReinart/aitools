from enum import Enum

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

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
    file: UploadFile | None = None,
) -> dict[str, str]:
    """Upload an OpenAPI spec (YAML or JSON)"""
    if file is None:
        file = File(...)
    if file.content_type not in CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a JSON or YAML file.",
        )

    # TODO: Implement file processing and return a unique ID
    raise NotImplementedError("Upload endpoint not implemented")


@router.get("/spec/{spec_id}/summary")
async def get_summary(_spec_id: str) -> dict[str, str]:
    """Retrieve a plain-English summary of the spec"""
    # TODO: Implement summary retrieval
    raise NotImplementedError("Summary endpoint not implemented")


@router.get("/spec/{spec_id}/export")
async def export_summary(
    _spec_id: str,
    file_format: ExportFormat = ExportFormat.MARKDOWN,
) -> HTMLResponse | FileResponse:
    """Export the summary in various formats"""
    # TODO: Implement export functionality
    if file_format == ExportFormat.HTML:
        return HTMLResponse("<h1>API Summary</h1>")
    if file_format == ExportFormat.MARKDOWN:
        return FileResponse(
            path="summary.md",
            media_type="text/markdown",
            filename=f"api-summary-{_spec_id}.md",
        )
    # DOCX
    return FileResponse(
        path="summary.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"api-summary-{_spec_id}.docx",
    )
