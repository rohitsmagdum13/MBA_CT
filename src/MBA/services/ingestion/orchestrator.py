"""
CSV ingestion orchestrator for RDS data loading.

This module provides the CSVIngestor class that orchestrates the complete
pipeline for loading CSV files into MySQL RDS with automatic schema management,
batch processing, and comprehensive error handling.
"""

from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
import traceback

from MBA.core.exceptions import (
    DataIngestionError,
    SchemaInferenceError,
    FileDiscoveryError,
)
from MBA.core.logging_config import get_logger
from MBA.services.database.client import RDSClient
from MBA.services.database.schema_inferrer import SchemaInferrer
from MBA.services.database.schema_manager import SchemaManager
from MBA.services.ingestion.loader import CSVLoader
from MBA.services.ingestion.batch_processor import BatchProcessor

logger = get_logger(__name__)


class CSVIngestor:
    """CSV → MySQL ingestion orchestrator."""

    def __init__(
        self,
        rds_client: Optional[RDSClient] = None,
        schema_inferrer: Optional[SchemaInferrer] = None,
        chunk_size: Optional[int] = None,
        skip_duplicates: bool = False,
        truncate_before_load: bool = False,
    ):
        self.rds_client = rds_client or RDSClient()
        self.schema_inferrer = schema_inferrer or SchemaInferrer()
        self.schema_manager = SchemaManager(self.rds_client, self.schema_inferrer)
        self.csv_loader = CSVLoader(
            self.rds_client, chunk_size, skip_duplicates, truncate_before_load
        )
        self.batch_processor = BatchProcessor(self)

        logger.info(
            "Initialized CSVIngestor: chunk_size=%s, skip_duplicates=%s, truncate=%s",
            chunk_size,
            skip_duplicates,
            truncate_before_load,
        )

    def ingest_csv(
        self, csv_path: Path, table_name: Optional[str] = None, update_schema: bool = True
    ) -> Dict[str, Any]:
        """
        Full pipeline: infer → create/update → load.
        
        Args:
            csv_path: CSV file to ingest
            table_name: Optional target table override
            update_schema: If True, add new columns to existing tables
            
        Returns:
            Results with success flag, table name, and load statistics
        """
        # Ensure absolute path for Lambda compatibility
        csv_path = csv_path.resolve()
        
        if not csv_path.exists():
            raise FileDiscoveryError(
                f"CSV file not found: {csv_path}", details={"path": str(csv_path)}
            )

        logger.info("Starting CSV ingestion: %s", csv_path.name)
        pipeline_start = datetime.now()

        try:
            # 1) Infer schema
            logger.info("Step 1/3: Inferring schema…")
            schema = self.schema_inferrer.infer_schema(
                csv_path, add_metadata_columns=True
            )
            if table_name:
                schema["table_name"] = table_name

            # 2) Ensure table exists and is compatible
            logger.info("Step 2/3: Ensuring table schema…")
            final_table_name = self.schema_manager.ensure_table_schema(
                schema, update_if_exists=update_schema
            )

            # 3) Build original→normalized column mapping (exclude metadata)
            column_mapping = {
                c["original_name"]: c["name"]
                for c in schema["columns"]
                if c["original_name"] not in ("ingestion_timestamp", "source_file")
            }

            # 4) Load CSV
            logger.info("Step 3/3: Loading data…")
            load_results = self.csv_loader.load_csv_to_table(
                csv_path, final_table_name, column_mapping
            )

            pipeline_duration = (datetime.now() - pipeline_start).total_seconds()
            results = {
                "success": load_results["success"],
                "csv_file": csv_path.name,
                "table_name": final_table_name,
                "columns_inferred": len(schema["columns"]),
                "load_results": load_results,
                "pipeline_duration_seconds": round(pipeline_duration, 2),
            }

            if results["success"]:
                logger.info(
                    "✓ CSV ingestion successful: %s → %s (%d rows in %.2fs)",
                    csv_path.name,
                    final_table_name,
                    load_results["rows_loaded"],
                    pipeline_duration,
                )
            else:
                logger.warning(
                    "⚠ CSV ingestion completed with errors: %d rows failed",
                    load_results["rows_failed"],
                )

            return results

        except (SchemaInferenceError, DataIngestionError) as e:
            logger.error("CSV ingestion failed: %s", e.message, extra={"details": e.details})
            raise
        except Exception as e:
            logger.error("Unexpected error during ingestion: %s", str(e))
            logger.debug(traceback.format_exc())
            raise DataIngestionError(
                f"CSV ingestion failed: {str(e)}",
                details={"csv_path": str(csv_path), "error": str(e)},
            )

    def ingest_directory(
        self, directory: Path, file_pattern: str = "*.csv", continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """Ingest all CSV files under a directory."""
        return self.batch_processor.ingest_directory(directory, file_pattern, continue_on_error)