"""
Centralized configuration management using Pydantic.

This module defines the Settings class which loads and validates application
configuration from environment variables or .env file.

Module Input:
    - Environment variables from OS
    - .env file in project root (optional)
    - Default values defined in class

Module Output:
    - Validated configuration object (singleton)
    - Helper methods for bucket/prefix resolution
    - Database connection strings
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

from .exceptions import ValidationError


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    
    Uses Pydantic's BaseSettings to provide validated configuration with
    automatic type conversion and environment variable loading. Supports
    both development (.env file) and production (environment variables)
    configuration methods.
    
    Attributes:
        AWS Configuration:
            aws_access_key_id (Optional[str]): AWS access key for API calls
            aws_secret_access_key (Optional[str]): AWS secret key
            aws_default_region (str): Default AWS region (default: "us-east-1")
            aws_profile (Optional[str]): Named AWS profile to use

        AWS Bedrock Configuration:
            bedrock_model_id (str): Bedrock model ID for LLM inference

        S3 Configuration:
            s3_bucket_mba (str): S3 bucket for MBA data files
            s3_prefix_mba (str): Key prefix for MBA files (must end with /)
            s3_prefix_csv (str): Key prefix for CSV files (must end with /)
            s3_sse (str): Server-side encryption type (default: "AES256")
            
        RDS Configuration:
            rds_host (str): MySQL RDS endpoint hostname
            rds_port (int): MySQL port (default: 3306)
            rds_database (str): Database name
            rds_username (str): Database user
            rds_password (str): Database password
            rds_params (str): Additional connection parameters
            rds_pool_size (int): Connection pool size (default: 5)
            rds_pool_max_overflow (int): Max overflow connections (default: 10)
            
        CSV Ingestion Configuration:
            csv_data_dir (Path): Local CSV directory (default: "data/csv")
            csv_chunk_size (int): Rows per batch insert (default: 1000)
            csv_encoding (str): Default CSV encoding (default: "utf-8")
            
        Logging Configuration:
            log_level (str): Minimum log level (default: "INFO")
            log_dir (Path): Directory for log files (default: "logs")
            log_file (str): Log file name (default: "app.log")
    """

    # ---------------- AWS Configuration ----------------
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_default_region: str = "us-east-1"
    aws_profile: Optional[str] = None

    # ---------------- AWS Bedrock Configuration ----------------
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # ---------------- S3 Buckets ----------------
    s3_bucket_mba: str = "mb-assistant-bucket"

    # ---------------- S3 Prefixes ----------------
    s3_prefix_mba: str = "mba/"
    s3_prefix_csv: str = "csv/"

    # Optional: server-side encryption for uploads (AES256 or aws:kms)
    s3_sse: str = "AES256"

    # ---------------- Textract Configuration ----------------
    pdf_prefix: str = "mba/pdf/"
    output_prefix: str = "mba/textract-output/"
    textract_features: str = "TABLES,FORMS"  # Comma-separated
    textract_max_seconds: int = 240  # Max polling time
    textract_backoff_start_sec: float = 2.0
    textract_backoff_max_sec: float = 12.0

    # ---------------- RDS Configuration ----------------
    rds_host: str = "mba-mysql-db.conaisaskh5d.us-east-1.rds.amazonaws.com"
    rds_port: int = 3306
    rds_database: str = "mba_db"
    rds_username: str = "admin"
    rds_password: str = "Admin12345"
    rds_params: str = "charset=utf8mb4"
    
    # Connection pooling
    rds_pool_size: int = 5
    rds_pool_max_overflow: int = 10

    # ---------------- CSV Ingestion ----------------
    csv_data_dir: Path = Path("data/csv")
    csv_chunk_size: int = 1000
    csv_encoding: str = "utf-8"

    # ---------------- Logging ----------------
    log_level: str = "INFO"
    log_dir: Path = Path("logs")
    log_file: str = "app.log"

    # ---------------- Qdrant Configuration ----------------
    qdrant_url: str = "https://6cff52b1-a13c-4049-9a3e-8993feb95210.us-east-1-1.aws.cloud.qdrant.io:6333"
    qdrant_api_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.TdRHOh7YMp-CgFtvhcdQq01BBS3lLyacvhdDEHmKK-U"
    qdrant_collection: str = "benefit_coverage_rag_index"
    embedding_dimension: int = 1024

    # ---------------- Pydantic Settings ----------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- Helper Methods ----------------
    def get_bucket(self, scope: str) -> str:
        """
        Get bucket name for given scope.
        
        Maps scope identifier to corresponding S3 bucket name.
        
        Args:
            scope (str): Scope identifier ("mba")
            
        Returns:
            str: S3 bucket name for the scope
            
        Raises:
            ValidationError: If scope is not "mba"
        """
        s = scope.strip().lower()
        if s == "mba":
            return self.s3_bucket_mba
        raise ValidationError(
            f"Invalid scope: {scope}",
            details={"valid_scopes": ["mba"], "provided_scope": scope}
        )

    def get_prefix(self, scope: str) -> str:
        """
        Get S3 prefix for given scope.
        
        Maps scope identifier to corresponding S3 key prefix.
        
        Args:
            scope (str): Scope identifier ("mba" or "csv")
            
        Returns:
            str: S3 prefix ending with '/'
            
        Raises:
            ValidationError: If scope is not valid
        """
        s = scope.strip().lower()
        if s == "mba":
            return self.s3_prefix_mba
        elif s == "csv":
            return self.s3_prefix_csv
        raise ValidationError(
            f"Invalid scope: {scope}",
            details={"valid_scopes": ["mba", "csv"], "provided_scope": scope}
        )
    
    def get_database_url(self, driver: str = "pymysql") -> str:
        """
        Build SQLAlchemy database URL.
        
        Constructs connection URL with proper encoding of credentials
        and parameters.
        
        Args:
            driver (str): MySQL driver name (default: "pymysql")
            
        Returns:
            str: SQLAlchemy connection URL
            
        Example:
            >>> settings.get_database_url()
            'mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4'
        """
        password_encoded = quote_plus(self.rds_password)
        
        url = (
            f"mysql+{driver}://{self.rds_username}:{password_encoded}"
            f"@{self.rds_host}:{self.rds_port}/{self.rds_database}"
        )
        
        if self.rds_params:
            url += f"?{self.rds_params}"
        
        return url
    
    def get_database_config(self) -> dict[str, any]:
        """
        Get database connection configuration as dictionary.
        
        Returns connection parameters suitable for direct MySQL
        connector usage.
        
        Returns:
            dict[str, any]: Database connection parameters
            
        Example:
            >>> config = settings.get_database_config()
            >>> connection = mysql.connector.connect(**config)
        """
        return {
            "host": self.rds_host,
            "port": self.rds_port,
            "database": self.rds_database,
            "user": self.rds_username,
            "password": self.rds_password,
            "charset": "utf8mb4"
        }


# Singleton instance shared across the app
settings = Settings()