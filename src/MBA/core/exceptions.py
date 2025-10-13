"""
Custom exceptions for the MBA ingestion system.

This module defines a hierarchy of domain-specific exceptions to provide
consistent error handling across ingestion components.

Module Input:
    - Error conditions from various system components
    - Optional error details as dictionaries

Module Output:
    - Structured exception objects with message and details
    - Consistent error interface for catch blocks
"""
from typing import Optional, Any


class MBAIngestionError(Exception):
    """
    Base exception for all MBA ingestion errors.
    
    Provides a common base class for all domain-specific exceptions
    in the MBA ingestion system, enabling consistent error handling
    and reporting across modules.
    
    Attributes:
        message (str): Human-readable error description
        details (dict[str, Any]): Optional structured error details
    """
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        """
        Initialize exception with message and optional details.
        
        Args:
            message (str): Human-readable error description
            details (Optional[dict[str, Any]]): Additional structured error context
            
        Side Effects:
            - Calls parent Exception.__init__
            - Stores message and details as instance attributes
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigError(MBAIngestionError):
    """
    Raised when configuration is invalid or missing.
    
    Used for errors related to missing environment variables, invalid
    configuration values, or inaccessible configuration files.
    
    Common scenarios:
        - Invalid scope values (not 'mba' or 'policy')
        - Missing required AWS credentials
        - Invalid bucket names or regions
        - Missing RDS connection parameters
    """
    pass


class UploadError(MBAIngestionError):
    """
    Raised when S3 upload fails.
    
    Indicates failures in the S3 upload process including network errors,
    permission issues, or exhausted retry attempts.
    
    Common scenarios:
        - AWS credentials not found
        - Access denied to S3 bucket
        - Network timeouts after retries
        - Invalid S3 key formats
    """
    pass


class FileDiscoveryError(MBAIngestionError):
    """
    Raised when file discovery or processing fails.
    
    Used for errors during filesystem scanning, file reading, or
    path resolution operations.
    
    Common scenarios:
        - Input directory doesn't exist
        - Permission denied on directory
        - Symlink resolution failures
        - Invalid file paths
    """
    pass


class QueueError(MBAIngestionError):
    """
    Raised when queue operations fail.
    
    Indicates failures in the job queue system used by microservices mode.
    
    Common scenarios:
        - Queue full conditions
        - Serialization failures
        - Queue corruption
    """
    pass


class DatabaseError(MBAIngestionError):
    """
    Raised when database operations fail.
    
    Used for errors during database connection, query execution,
    or transaction management.
    
    Common scenarios:
        - Connection failures to RDS
        - SQL syntax errors
        - Constraint violations
        - Transaction deadlocks
        - Connection pool exhaustion
    """
    pass


class SchemaInferenceError(MBAIngestionError):
    """
    Raised when schema inference from CSV fails.
    
    Indicates failures during CSV parsing, column type detection,
    or schema generation.
    
    Common scenarios:
        - Malformed CSV files
        - Inconsistent column types
        - Invalid table/column names
        - Empty or header-less CSVs
    """
    pass


class DataIngestionError(MBAIngestionError):
    """
    Raised when data ingestion to database fails.
    
    Used for errors during bulk data loading, row validation,
    or data transformation operations.
    
    Common scenarios:
        - Type conversion failures
        - Constraint violations during insert
        - Duplicate key errors
        - Invalid data values
    """
    pass