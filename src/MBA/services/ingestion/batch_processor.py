"""
Batch processing for multiple CSV files.

Handles directory-level ingestion with error handling and reporting.
"""

from pathlib import Path
from typing import Dict, List, Any

from MBA.core.exceptions import FileDiscoveryError
from MBA.core.logging_config import get_logger

logger = get_logger(__name__)


class BatchProcessor:
    """Handles batch processing of multiple CSV files."""

    def __init__(self, ingestor):
        """Initialize with a CSV ingestor instance."""
        self.ingestor = ingestor

    def ingest_directory(
        self, directory: Path, file_pattern: str = "*.csv", continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest all CSV files under a directory.
        
        Args:
            directory: Directory path
            file_pattern: Glob pattern for CSV selection
            continue_on_error: Continue upon individual file failures
            
        Returns:
            Batch summary with per-file results and errors
        """
        if not directory.exists():
            raise FileDiscoveryError(
                f"Directory not found: {directory}", details={"path": str(directory)}
            )
        if not directory.is_dir():
            raise FileDiscoveryError(
                f"Path is not a directory: {directory}", details={"path": str(directory)}
            )

        csv_files = list(directory.glob(file_pattern))
        if not csv_files:
            logger.warning("No CSV files found in %s", directory)
            return {
                "total_files": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
                "errors": [],
            }

        logger.info("Starting batch ingestion: %d files from %s", len(csv_files), directory)

        successful = failed = 0
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for idx, csv_file in enumerate(csv_files, 1):
            logger.info("Processing file %d/%d: %s", idx, len(csv_files), csv_file.name)
            try:
                result = self.ingestor.ingest_csv(csv_file)
                results.append(result)
                if result["success"]:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                error_info = {
                    "file": csv_file.name,
                    "error": str(e),
                    "type": type(e).__name__,
                }
                errors.append(error_info)
                logger.error("Failed to ingest %s: %s", csv_file.name, str(e))
                if not continue_on_error:
                    logger.error("Halting batch ingestion due to error")
                    break

        batch_results = {
            "total_files": len(csv_files),
            "successful": successful,
            "failed": failed,
            "results": results,
            "errors": errors,
        }

        logger.info(
            "Batch ingestion complete: %d/%d successful, %d failed",
            successful, len(csv_files), failed,
        )
        return batch_results