"""Logging utility for the bot."""

import logging
import sys
from typing import Optional

# Configure root logger
_logger: Optional[logging.Logger] = None


def get_logger(name: str = "bot") -> logging.Logger:
    """Get or create a logger instance."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger(name)
        _logger.setLevel(logging.INFO)
        
        # Create console handler if not already configured
        if not _logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            _logger.addHandler(handler)
    
    return _logger


def log_error(location: str, message: str, exc_info: bool = False) -> None:
    """Log an error message."""
    logger = get_logger()
    logger.error(f"[{location}] {message}", exc_info=exc_info)


def log_warning(location: str, message: str) -> None:
    """Log a warning message."""
    logger = get_logger()
    logger.warning(f"[{location}] {message}")


def log_info(location: str, message: str) -> None:
    """Log an info message."""
    logger = get_logger()
    logger.info(f"[{location}] {message}")


def log_debug(location: str, message: str) -> None:
    """Log a debug message."""
    logger = get_logger()
    logger.debug(f"[{location}] {message}")

