"""Standalone API processing tasks."""

from celery.canvas import Signature

from src.api.exceptions import BrokerError


def verify_broker_connection(chain: Signature) -> None:
    """Verify broker connection."""
    try:
        connection = chain.app.connection()
        connection.ensure_connection(max_retries=3, interval_start=1)
    except ConnectionError as e:
        raise BrokerError() from e
