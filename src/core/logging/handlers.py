"""Logging handlers and frame utilities."""

import inspect
import logging
from types import FrameType

from loguru import logger


def get_caller_info() -> tuple[str, str, int]:
    """Get information about the calling frame.

    Returns:
        Tuple containing (filename, function_name, line_number)
    """
    caller_frame: FrameType | None = inspect.currentframe()
    if caller_frame is None:
        return "unknown", "unknown", 0

    # Get the frame of our caller (one up from current)
    caller_frame = caller_frame.f_back
    if caller_frame is None:
        return "unknown", "unknown", 0

    # Extract information
    frame_info = inspect.getframeinfo(caller_frame)
    return (
        frame_info.filename,
        frame_info.function,
        frame_info.lineno if frame_info.lineno is not None else 0,
    )


def trim_message(message: str, max_length: int = 1000) -> str:
    """Trim a message if it exceeds the maximum length.

    Args:
        message: The message to trim
        max_length: Maximum length before trimming

    Returns:
        Trimmed message
    """
    if len(message) > max_length:
        return message[:max_length] + "... (truncated)"
    return message


class InterceptHandler(logging.Handler):
    """Intercepts standard library logging and redirects to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record.

        Args:
            record: The log record to emit
        """
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where originated the logged message
        frame: FrameType | None = inspect.currentframe()
        depth = 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        # Trim the message if it's too long
        message = trim_message(record.getMessage())

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            message,
        )
