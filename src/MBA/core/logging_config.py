"""
Centralized logging configuration for the application.

Provides standardized logging setup with console and rotating file handlers,
ensuring consistent log formatting across all modules.

Module Input:
    - Logger name strings from calling modules
    - Log messages from application code
    - Configuration parameters

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


class LoggerConfig:
    """Class to manage logger configuration and creation."""

    # Class variable to track configured loggers (prevents duplicate configuration)
    _configured_loggers = set()

    def __init__(
        self,
        log_level: int = logging.INFO,
        log_dir: str = "logs",
        log_file: str = "app.log",
        max_bytes: int = 10_485_760,  # 10MB
        backup_count: int = 5
    ):
        """
        Initialize logger configuration.

        Args:
            log_level: Minimum logging level (default: INFO)
            log_dir: Directory where log files are saved
            log_file: Name of the log file
            max_bytes: Maximum size of log file before rotation (10MB default)
            backup_count: Number of backup log files to keep
        """
        # Store configuration settings
        self.log_level = log_level
        self.log_dir = Path(log_dir)
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        # Check if running in AWS Lambda environment
        # Lambda sets these environment variables automatically
        self.is_lambda = (
            'AWS_EXECUTION_ENV' in os.environ or
            'AWS_LAMBDA_FUNCTION_NAME' in os.environ
        )

    def _create_formatter(self) -> logging.Formatter:
        """
        Create log formatter based on environment.

        Returns:
            logging.Formatter: Configured formatter object

        Note:
            - Lambda uses simpler format (CloudWatch adds timestamps)
            - Local uses full format with timestamp
        """
        if self.is_lambda:
            # Lambda already captures stdout to CloudWatch, use simpler format
            # CloudWatch automatically adds timestamps to all logs
            formatter = logging.Formatter(
                "%(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
            )
        else:
            # Local development format - includes timestamp
            # Format: "2024-01-15 10:30:45 | INFO | module:function:line | message"
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        return formatter

    def _create_console_handler(self) -> logging.StreamHandler:
        """
        Create console handler that outputs to stdout.

        Returns:
            logging.StreamHandler: Configured console handler

        Note:
            Console handler writes logs to terminal/console
        """
        # Create handler that writes to stdout (console/terminal)
        console_handler = logging.StreamHandler(sys.stdout)

        # Set the minimum log level for this handler
        console_handler.setLevel(self.log_level)

        # Apply the formatter to this handler
        console_handler.setFormatter(self._create_formatter())

        return console_handler

    def _create_file_handler(self) -> Optional[RotatingFileHandler]:
        """
        Create rotating file handler for local environments.

        Returns:
            RotatingFileHandler or None: File handler (None if in Lambda)

        Note:
            - Only created for non-Lambda environments
            - Automatically rotates when file reaches max_bytes
            - Keeps backup_count number of old log files
        """
        # Skip file handler in Lambda - Lambda uses CloudWatch for logs
        if self.is_lambda:
            return None

        # Create log directory if it doesn't exist
        # exist_ok=True prevents error if directory already exists
        self.log_dir.mkdir(exist_ok=True)

        # Build complete path to log file
        log_file_path = self.log_dir / self.log_file

        # Create rotating file handler
        # When file reaches max_bytes, it renames current file and starts new one
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count
        )

        # Set minimum log level for this handler
        file_handler.setLevel(self.log_level)

        # Apply formatter to this handler
        file_handler.setFormatter(self._create_formatter())

        return file_handler

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger with standardized configuration.

        Creates a logger instance with both console and rotating file handlers,
        using consistent formatting across the application. Prevents duplicate
        handler configuration on repeated calls.

        Args:
            name: Logger name, typically __name__ from calling module

        Returns:
            logging.Logger: Configured logger instance ready for use

        Side Effects:
            - Creates log directory if it doesn't exist
            - Adds logger name to _configured_loggers set
            - Creates handlers on first call for each logger

        Log Format:
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
            Example: "2024-01-15 10:30:45 | INFO | mba.cli:upload_single:145 | Upload complete"
        """
        # Check if this logger was already configured
        # If yes, return existing logger without reconfiguring
        if name in LoggerConfig._configured_loggers:
            return logging.getLogger(name)

        # Get logger instance from Python's logging system
        logger = logging.getLogger(name)

        # Set the base logging level for this logger
        logger.setLevel(self.log_level)

        # If logger already has handlers, return it without adding more
        # This prevents duplicate log messages
        if logger.hasHandlers():
            return logger

        # Add console handler (always present in all environments)
        console_handler = self._create_console_handler()
        logger.addHandler(console_handler)

        # Add file handler (only for non-Lambda environments)
        file_handler = self._create_file_handler()
        if file_handler is not None:
            logger.addHandler(file_handler)

        # Mark this logger as configured
        # This prevents duplicate configuration on future calls
        LoggerConfig._configured_loggers.add(name)

        return logger

    @staticmethod
    def setup_root_logger(log_level: int = logging.INFO):
        """
        Configure the root logger for libraries that use it.

        Sets up basic configuration for the root logger, which is inherited
        by third-party libraries that don't explicitly configure their loggers.

        Args:
            log_level: Minimum logging level (default: INFO)

        Side Effects:
            - Configures root logger with basicConfig
            - Sets format and level for all unconfigured loggers
        """
        # Configure root logger with basic settings
        # This affects all loggers that don't have explicit configuration
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


# Default logger configuration instance
_default_config = LoggerConfig()


# Convenience function for simple usage
def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with default configuration.

    Provides simple access to logging functionality.
    Most modules will use this function to get a logger.

    Args:
        name: Logger name, typically __name__ from calling module

    Returns:
        logging.Logger: Configured logger instance ready for use

    Example:
        from logger.custom_logger import get_logger

        logger = get_logger(__name__)
        logger.info("Application started")
        logger.error("Something went wrong")
    """
    # Use the default configuration instance
    return _default_config.get_logger(name)


# Test the logger when running this file directly
if __name__ == "__main__":
    # Create a logger using default configuration
    logger = get_logger(__name__)

    # Try different log levels
    logger.info("This is an info message")
    logger.warning("This is a warning")
    logger.error("This is an error")
    logger.debug("This is a debug message (won't show unless level is DEBUG)")