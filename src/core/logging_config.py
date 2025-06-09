import logging
import sys
from pathlib import Path
from typing import cast

from loguru import logger
from loguru._logger import Logger

from .config import settings


class ConsoleSink:
    """A custom sink for loguru that writes to stderr with proper encoding."""

    def __init__(self) -> None:
        self.stderr = sys.stderr
        self.encoding = self.stderr.encoding or "utf-8"

    def write(self, message: str) -> None:
        """Write a message to stderr.

        Args:
            message: The formatted log message to write.
        """
        try:
            self.stderr.write(message)
            self.stderr.flush()
        except Exception as e:
            # Fallback to basic output if stderr fails
            sys.stderr.write(f"Logging failed: {e}\n")
            sys.stderr.write(message)


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """Configure logging for both application and Celery."""
    # Remove default handler
    logger.remove()

    # Add custom console sink with proper formatting
    logger.add(
        ConsoleSink().write,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        ),
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Add file handler for all logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "app.log",
        rotation="1 day",
        retention="7 days",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        level=settings.LOG_LEVEL,
        backtrace=True,
        diagnose=True,
    )

    # Configure Celery logging to use loguru
    celery_logger = logging.getLogger("celery")
    celery_logger.handlers = []  # Remove default handlers
    celery_logger.addHandler(InterceptHandler())
    celery_logger.setLevel(logging.INFO)


def get_logger() -> Logger:
    """Get the configured logger instance.

    Returns:
        The configured loguru logger instance.
    """
    return cast(Logger, logger)


# Initialize logging
setup_logging()
