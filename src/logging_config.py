from loguru import logger
from .config import settings

logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level=settings.LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}",
)


def get_logger():
    return logger
