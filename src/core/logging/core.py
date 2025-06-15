"""Core logging functionality for the application."""

import logging
import sys
from datetime import datetime, timezone
from typing import Any

from loguru import logger  # type: ignore

from .config import LogConfig
from .formatters import setup_trimmed_logging
from .handlers import InterceptHandler, get_caller_info, trim_message


def get_logger(name: str | None = None) -> Any:  # noqa: ANN401
    """Get a logger instance.

    Args:
        name: Optional name for the logger. If None, will use caller information.

    Returns:
        A configured logger instance.
    """
    if name is None:
        filename, function_name, line_number = get_caller_info()
        name = f"{filename}:{function_name}:{line_number}"

    return logger.bind(context=name)


def setup_logging(config: LogConfig | None = None) -> None:
    """Set up logging configuration.

    Args:
        config: Optional logging configuration. If None, uses defaults.
    """
    if config is None:
        config = LogConfig()

    # Remove default handler
    logger.remove()

    # Add console handler with message trimming
    logger.add(
        sys.stderr,
        format=config.console_format,
        level=config.level,
        enqueue=True,
        diagnose=True,
        backtrace=True,
        filter=lambda record: record["extra"].get("message", "")
        == trim_message(record["extra"].get("message", "")),
    )

    # Add file handler with message trimming
    now = datetime.now(timezone.utc)
    log_file = config.log_dir / f"api_{now.strftime('%Y%m%d_%H%M%S')}.log"

    # Ensure we have a valid format string
    file_format = (
        config.file_format if config.file_format is not None else config.console_format
    )

    logger.add(
        str(log_file),
        format=file_format,
        level=config.level,
        rotation=config.rotation_interval,
        retention=f"{config.retention_days} days",
        compression="zip",
        enqueue=True,
        diagnose=True,
        backtrace=True,
        filter=lambda record: record["extra"].get("message", "")
        == trim_message(record["extra"].get("message", "")),
    )

    # Configure standard library logging to use loguru with message trimming
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Set up global message trimming
    setup_trimmed_logging()
