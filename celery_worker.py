"""Celery worker configuration."""

from src.core.celery_app import celery_app
from src.core.logging_config import setup_logging

# Export the Celery app instance
celery = celery_app


# Configure logging before starting worker
setup_logging()

if __name__ == "__main__":
    celery_app.start()
