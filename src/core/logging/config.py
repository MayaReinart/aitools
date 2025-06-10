"""Logging configuration dataclasses and utilities."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class LogConfig:
    """Configuration settings for logging."""

    level: str = "DEBUG"
    retention_days: int = 7
    rotation_interval: str = "1 day"
    log_dir: Path = Path("logs")
    console_format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    file_format: str | None = None

    def __post_init__(self) -> None:
        """Ensure log directory exists and set default file format."""
        self.log_dir.mkdir(exist_ok=True, parents=True)
        if self.file_format is None:
            self.file_format = self.console_format
