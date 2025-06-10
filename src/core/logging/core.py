"""Core logging functionality for the application."""

import logging
import sys
from datetime import datetime, timezone
from typing import Any

from loguru import logger  # type: ignore

from .config import LogConfig
from .handlers import InterceptHandler, get_caller_info


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

    # Add console handler
    logger.add(
        sys.stderr,
        format=config.console_format,
        level=config.level,
        enqueue=True,
        diagnose=True,
        backtrace=True,
    )

    # Add file handler
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
    )

    # Configure standard library logging to use loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
