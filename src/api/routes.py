from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, File, HTTPException, UploadFile

from src.tasks.tasks import summarize_doc_task

router = APIRouter(prefix="/api", tags=["api"])


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.post("/submit")
async def submit_file(
    file: UploadFile = None,
) -> dict[str, str]:
    if file is None:
        file = File(...)

    if file.content_type not in ["application/json", "text/plain"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a JSON or text file.",
        )

    # We don't expect the file to be large, so we can read it into memory
    content = await file.read()
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError as err:
        raise HTTPException(
            status_code=400,
            detail="File content must be valid UTF-8 text",
        ) from err

    # Submit the decoded content to Celery
    job_id = summarize_doc_task.delay(content_str)

    return {"status": "file uploaded successfully", "job_id": str(job_id)}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict[str, str | None]:
    result = AsyncResult(job_id)
    if result.ready():
        return {"status": result.status, "result": result.result}
    return {"status": result.status}
