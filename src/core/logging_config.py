import sys

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


# Remove default handler
logger.remove()

# Add custom sink with proper formatting
logger.add(
    ConsoleSink().write,
    level=settings.LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}",
    colorize=True,
)


def get_logger() -> Logger:
    """Get the configured logger instance.

    Returns:
        The configured loguru logger instance.
    """
    return logger
