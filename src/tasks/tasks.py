from celery import Task

from celery_worker import celery_app
from src.services.llm import summarize_doc


@celery_app.task(bind=True)
def summarize_doc_task(self: Task, content: str) -> str:
    try:
        return summarize_doc(content)
    except Exception as e:
        self.retry(exc=e, countdown=5, max_retries=3)
        raise  # This will never be reached, but makes mypy happy
