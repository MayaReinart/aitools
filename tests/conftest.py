"""Test configuration."""

from celery_worker import celery_app


def pytest_configure() -> None:
    """Configure test environment."""
    # Configure Celery for testing before any tests run
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=True,
        task_store_eager_result=True,
        broker_connection_retry=False,
        broker_connection_max_retries=0,
        task_remote_tracebacks=True,  # For better error messages
    )
