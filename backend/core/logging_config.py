import logging
import sys
from pathlib import Path
from backend.core.config import get_settings


def setup_logging() -> logging.Logger:
    """Configures structured console and file logging for ClauseGuard."""
    settings = get_settings()
    log_level = logging.DEBUG if settings.app_debug else logging.INFO

    # Create root logger for ClauseGuard
    logger = logging.getLogger("clauseguard")
    logger.setLevel(log_level)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Log format
    log_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # File Handler
    try:
        log_file = settings.storage_dir / "clauseguard.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"Warning: Could not configure file logging: {e}\n")

    return logger


# Global logger instance
logger = setup_logging()
