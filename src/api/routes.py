from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
