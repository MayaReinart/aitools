import shutil
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path


router = APIRouter(prefix="/api", tags=["api"])


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.post("/submit")
async def submit_file(file: UploadFile = File(...)):
    if file.content_type not in ["application/json", "text/plain"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a JSON or text file."
        )
    
    job_id = str(uuid4())

    file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"status": "file uploaded successfully", "job_id": job_id}
