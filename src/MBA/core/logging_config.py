"""
Centralized logging configuration for the MBA ingestion system.

Provides standardized logging setup with console and rotating file handlers,
ensuring consistent log formatting across all modules.

Module Input:
    - Logger name strings from calling modules
    - Log messages from application code
    - Configuration from settings module

Module Output:
    - Formatted log entries to console (stdout)
    - Formatted log entries to rotating file (logs/app.log)
    - Configured logger instances for modules
"""
import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from .settings import settings

# Track configured loggers to avoid duplicate configuration
_configured_loggers = set()


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with standardized configuration.
    
    Creates a logger instance with both console and rotating file handlers,
    using consistent formatting across the application. Prevents duplicate
    handler configuration on repeated calls.
    
    Args:
        name (str): Logger name, typically __name__ from calling module
        
    Returns:
        logging.Logger: Configured logger instance ready for use
        
    Side Effects:
        - Creates log directory if it doesn't exist
        - Adds logger name to _configured_loggers set
        - Creates handlers on first call for each logger
        
    Log Format:
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        Example: "2024-01-15 10:30:45 | INFO     | mba.cli:upload_single:145 | Upload complete"
    """
    # Check if running in Lambda
    is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ
    
    if name in _configured_loggers:
        return logging.getLogger(name)
    
    logger = logging.getLogger(name)
    logger.setLevel(settings.log_level)
    
    if logger.hasHandlers():
        return logger
    
    # Define log format
    if is_lambda:
        # Lambda already captures stdout to CloudWatch, use simpler format
        formatter = logging.Formatter(
            "%(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Console handler - outputs to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler - only for non-Lambda environments
    if not is_lambda:
        settings.log_dir.mkdir(exist_ok=True)
        log_file_path = settings.log_dir / settings.log_file
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10_485_760,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(settings.log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    _configured_loggers.add(name)
    return logger


def setup_root_logger():
    """
    Configure the root logger for libraries that use it.
    
    Sets up basic configuration for the root logger, which is inherited
    by third-party libraries that don't explicitly configure their loggers.
    
    Input:
        None (reads configuration from settings)
        
    Output:
        None (configures logging.root)
        
    Side Effects:
        - Configures root logger with basicConfig
        - Sets format and level for all unconfigured loggers
    """
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )