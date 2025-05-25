from contextlib import asynccontextmanager
from fastapi import FastAPI
from .core.logging_config import get_logger

from .api.routes import router as api_router

logger = get_logger()
app = FastAPI(title="API Introspection", version="0.1.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting API Introspection Service")
    yield
    logger.info("Shutting down API Introspection Service")


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
