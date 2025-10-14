"""
S3 client for reliable file uploads with retry logic and metadata support.

This module provides a robust S3Client class for uploading files to AWS S3
with automatic MIME type detection, configurable metadata, and exponential
backoff retry logic for transient failures.

Module Input:
    - File paths from local filesystem
    - S3 bucket names and key prefixes
    - Optional metadata dictionaries
    - AWS credentials from settings

Module Output:
    - Uploaded files to S3 with correct content types
    - S3 URIs for uploaded objects
    - Upload status and error details via logging
"""

import mimetypes
import os
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from MBA.core.exceptions import UploadError, ConfigError
from MBA.core.logging_config import get_logger
from MBA.core.settings import settings

logger = get_logger(__name__)


class S3Client:
    """
    Robust S3 client with automatic retries and MIME detection.
    
    Provides reliable file upload operations to AWS S3 with intelligent
    MIME type detection, optional metadata attachment, and exponential
    backoff retry logic for handling transient network failures.
    
    The client uses AWS credentials from settings and supports both
    single-file and batch upload operations.
    
    Attributes:
        bucket (str): Target S3 bucket name
        prefix (str): S3 key prefix for all uploads
        max_retries (int): Maximum retry attempts for failed uploads
        retry_delay (float): Initial delay in seconds between retries
        _s3_client: Boto3 S3 client instance
        
    Thread Safety:
        Not thread-safe. Create separate instances for concurrent use.
    """
    
    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize S3 client with bucket and upload configuration.
        
        Creates a boto3 S3 client using credentials from settings module.
        Falls back to IAM role/instance profile if explicit credentials
        are not provided.
        
        Args:
            bucket (str): Target S3 bucket name
            prefix (str): S3 key prefix (default: "")
            max_retries (int): Maximum upload retry attempts (default: 3)
            retry_delay (float): Initial retry delay in seconds (default: 1.0)
            
        Raises:
            ConfigError: If AWS credentials are invalid or bucket is empty
            
        Side Effects:
            - Creates boto3 S3 client with session credentials
            - Logs client initialization
        """
        if not bucket:
            raise ConfigError("S3 bucket name cannot be empty")
            
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        try:
            # CRITICAL FIX: Detect if running in Lambda
            is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ
            
            if is_lambda:
                # In Lambda: Use execution role automatically (NO explicit credentials)
                session = boto3.Session(region_name=settings.aws_default_region)
                logger.info("Running in AWS Lambda - using execution role for S3")
            else:
                # Running locally: Use credentials from settings if available
                session_kwargs = {}
                if settings.aws_profile:
                    session_kwargs["profile_name"] = settings.aws_profile
                elif settings.aws_access_key_id and settings.aws_secret_access_key:
                    session_kwargs.update({
                        "aws_access_key_id": settings.aws_access_key_id,
                        "aws_secret_access_key": settings.aws_secret_access_key
                    })
                
                session = boto3.Session(
                    region_name=settings.aws_default_region,
                    **session_kwargs
                )
                logger.info("Running locally - using credentials from settings")
            
            self._s3_client = session.client("s3")
            
            logger.info(
                f"Initialized S3Client for bucket '{bucket}' with prefix '{self.prefix}'"
            )
            
        except Exception as e:
            raise ConfigError(
                "Failed to initialize S3 client",
                details={"error": str(e), "bucket": bucket}
            )
    
    def _detect_content_type(self, file_path: Path) -> str:
        """
        Detect MIME type for file based on extension.
        
        Uses Python's mimetypes module to infer content type from file
        extension. Falls back to binary octet-stream for unknown types.
        
        Args:
            file_path (Path): Path to file for type detection
            
        Returns:
            str: MIME type string (e.g., "application/pdf", "text/plain")
            
        Example:
            >>> client._detect_content_type(Path("doc.pdf"))
            'application/pdf'
        """
        content_type, _ = mimetypes.guess_type(str(file_path))
        return content_type or "application/octet-stream"
    
    def _build_s3_key(self, file_path: Path, custom_key: Optional[str] = None) -> str:
        """
        Build S3 object key from file path or custom key.
        
        Constructs full S3 key by combining configured prefix with either
        a custom key or the file's name.
        
        Args:
            file_path (Path): Source file path
            custom_key (Optional[str]): Custom key override (default: None)
            
        Returns:
            str: Complete S3 object key including prefix
            
        Example:
            >>> client.prefix = "mba/documents/"
            >>> client._build_s3_key(Path("report.pdf"))
            'mba/documents/report.pdf'
        """
        if custom_key:
            return f"{self.prefix}{custom_key.lstrip('/')}"
        return f"{self.prefix}{file_path.name}"
    
    def upload_file(
        self,
        file_path: Path,
        s3_key: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload single file to S3 with retry logic.
        
        Uploads a file to S3 with automatic MIME type detection, optional
        metadata, and exponential backoff retry for transient failures.
        
        Args:
            file_path (Path): Local file to upload
            s3_key (Optional[str]): Custom S3 key (default: uses filename)
            metadata (Optional[Dict[str, str]]): Custom metadata tags
            content_type (Optional[str]): Override MIME type detection
            
        Returns:
            str: S3 URI of uploaded object (s3://bucket/key)
            
        Raises:
            UploadError: If file doesn't exist or upload fails after retries
            
        Side Effects:
            - Uploads file to S3
            - Logs upload progress and errors
            - Applies server-side encryption from settings
            
        Example:
            >>> client.upload_file(
            ...     Path("contract.pdf"),
            ...     metadata={"document_type": "contract", "year": "2024"}
            ... )
            's3://my-bucket/mba/contract.pdf'
        """
        # Validate file exists
        if not file_path.exists():
            raise UploadError(
                f"File not found: {file_path}",
                details={"file_path": str(file_path)}
            )
        
        if not file_path.is_file():
            raise UploadError(
                f"Path is not a file: {file_path}",
                details={"file_path": str(file_path)}
            )
        
        # Build S3 key and detect content type
        key = self._build_s3_key(file_path, s3_key)
        detected_type = content_type or self._detect_content_type(file_path)
        
        # Prepare upload parameters
        extra_args = {
            "ContentType": detected_type,
            "ServerSideEncryption": settings.s3_sse
        }
        
        if metadata:
            extra_args["Metadata"] = metadata
        
        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Uploading {file_path.name} to s3://{self.bucket}/{key} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                
                self._s3_client.upload_file(
                    str(file_path),
                    self.bucket,
                    key,
                    ExtraArgs=extra_args
                )
                
                s3_uri = f"s3://{self.bucket}/{key}"
                logger.info(f"Successfully uploaded {file_path.name} to {s3_uri}")
                return s3_uri
                
            except (ClientError, BotoCoreError) as e:
                last_error = e
                error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "Unknown")
                
                logger.warning(
                    f"Upload attempt {attempt + 1} failed for {file_path.name}: "
                    f"{error_code} - {str(e)}"
                )
                
                # Don't retry on permanent errors
                if error_code in ["NoSuchBucket", "AccessDenied", "InvalidAccessKeyId"]:
                    break
                
                # Exponential backoff before retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
        
        # All retries exhausted
        raise UploadError(
            f"Failed to upload {file_path.name} after {self.max_retries} attempts",
            details={
                "file_path": str(file_path),
                "s3_key": key,
                "last_error": str(last_error)
            }
        )
    
    def upload_files(
        self,
        file_paths: List[Path],
        metadata_fn: Optional[callable] = None,
        continue_on_error: bool = True
    ) -> Tuple[List[str], List[Dict]]:
        """
        Upload multiple files to S3 with batch processing.
        
        Processes a list of files for upload with optional per-file metadata
        generation. Can continue processing after individual failures or
        halt on first error.
        
        Args:
            file_paths (List[Path]): List of local files to upload
            metadata_fn (Optional[callable]): Function returning metadata dict
                for each file: metadata_fn(file_path: Path) -> Dict[str, str]
            continue_on_error (bool): Continue after individual upload failures
                (default: True)
                
        Returns:
            Tuple[List[str], List[Dict]]: 
                - List of S3 URIs for successful uploads
                - List of error dicts with keys: file_path, error, details
                
        Side Effects:
            - Uploads files to S3
            - Logs batch progress and summary
            
        Example:
            >>> def add_metadata(path: Path) -> Dict[str, str]:
            ...     return {"source": "batch_import", "filename": path.name}
            >>> 
            >>> uris, errors = client.upload_files(
            ...     [Path("doc1.pdf"), Path("doc2.pdf")],
            ...     metadata_fn=add_metadata
            ... )
            >>> print(f"Uploaded {len(uris)} files, {len(errors)} errors")
        """
        logger.info(f"Starting batch upload of {len(file_paths)} files")
        
        successful_uris = []
        errors = []
        
        for idx, file_path in enumerate(file_paths, 1):
            logger.info(f"Processing file {idx}/{len(file_paths)}: {file_path.name}")
            
            try:
                # Generate metadata if function provided
                metadata = metadata_fn(file_path) if metadata_fn else None
                
                # Upload file
                s3_uri = self.upload_file(file_path, metadata=metadata)
                successful_uris.append(s3_uri)
                
            except UploadError as e:
                error_info = {
                    "file_path": str(file_path),
                    "error": e.message,
                    "details": e.details
                }
                errors.append(error_info)
                
                logger.error(
                    f"Failed to upload {file_path.name}: {e.message}",
                    extra={"error_details": e.details}
                )
                
                if not continue_on_error:
                    logger.error("Halting batch upload due to error")
                    break
        
        # Log summary
        logger.info(
            f"Batch upload complete: {len(successful_uris)} successful, "
            f"{len(errors)} failed"
        )
        
        return successful_uris, errors