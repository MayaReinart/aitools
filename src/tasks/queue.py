from datetime import time
from loguru import logger
from celery_worker import celery_app


def enqueue_job(job_id: str, file_path: str):
    logger.info(f"Enqueued job {job_id} for file {file_path}")
    # TODO: Add to Celery later


@celery_app.task(bind=True)
def summarize_doc(self, content: str) -> str:
    # Replace this with LLM logic later
    time.sleep(5)  # simulate heavy work
    return f"Summary: {content[:50]}..."
