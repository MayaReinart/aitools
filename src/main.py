from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import router as api_router
from .core.logging_config import get_logger

logger = get_logger()
app = FastAPI(title="API Introspection", version="0.1.0")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("🚀 Starting API Introspection Service")
    yield
    logger.info("Shutting down API Introspection Service")


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
