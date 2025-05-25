from loguru import logger


def enqueue_job(job_id: str, file_path: str):
    logger.info(f"Enqueued job {job_id} for file {file_path}")
    # TODO: Add to Redis queue or Celery later
