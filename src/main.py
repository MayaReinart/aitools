"""Main application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger  # type: ignore

from src.api.routes import router
from src.core.logging import setup_logging

# Set up logging
setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("🚀 Starting API Introspection Service")
    yield
    logger.info("Shutting down API Introspection Service")


app = FastAPI(
    lifespan=lifespan,
    title="API Introspection Service",
    description="Service for analyzing OpenAPI specifications",
    version="0.1.0",
)

# Mount the static files directory
web_dir = Path(__file__).parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


# Serve index.html at the root
@app.get("/")
async def read_root() -> FileResponse:
    return FileResponse(str(web_dir / "index.html"))


# Add a simple health check that doesn't depend on external services
@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy"}


# Include routers
app.include_router(router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
