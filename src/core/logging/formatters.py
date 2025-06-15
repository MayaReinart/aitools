"""Custom log formatters."""

from typing import Any

from loguru import logger

from .handlers import trim_message


def trim_long_message(record: dict[str, Any]) -> None:
    """Trim long messages in log records.

    Args:
        record: The log record to process
    """
    # Process all string fields that might contain long messages
    for field in ["message", "exception"]:
        # Check extra dict
        if field in record["extra"]:
            value = record["extra"][field]
            if isinstance(value, str):
                record["extra"][field] = trim_message(value, max_length=500)

        # Check record directly
        if field in record:
            value = record[field]
            if isinstance(value, str):
                record[field] = trim_message(value, max_length=500)


def setup_trimmed_logging() -> None:
    """Set up logging with message trimming."""
    logger.configure(patcher=trim_long_message)  # type: ignore
