"""
CSV ingestion orchestrator for RDS data loading.

This module provides the CSVIngestor class that orchestrates the complete
pipeline for loading CSV files into MySQL RDS with automatic schema management,
batch processing, and comprehensive error handling.

Module Input:
    - CSV file paths from local filesystem or S3
    - Configuration from settings module
    - RDS connection parameters

Module Output:
    - Loaded data in MySQL tables
    - Ingestion statistics and error reports
    - Schema creation/modification logs
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import traceback

import pandas as pd

from MBA.core.exceptions import (
    DataIngestionError,
    SchemaInferenceError,
    DatabaseError,
    FileDiscoveryError,
)
from MBA.core.logging_config import get_logger
from MBA.core.settings import settings
from MBA.services.rds_client import RDSClient
from MBA.services.schema_infer import SchemaInferrer

logger = get_logger(__name__)


class CSVIngestor:
    """
    CSV → MySQL ingestion orchestrator.

    Responsibilities:
    - Infer schema and create/alter target table.
    - Stream CSV in chunks and perform batch inserts.
    - Convert NaNs to NULLs, add metadata columns.
    - Capture row/chunk-level errors with capped error list.

    Attributes:
        rds_client: Database client instance (connection pooled).
        schema_inferrer: Schema inference engine.
        chunk_size: Rows per batch insert.
        skip_duplicates: Use INSERT IGNORE to skip duplicates.
        truncate_before_load: TRUNCATE table before loading.

    Thread Safety:
        Not thread-safe. Create separate instances for concurrent use.
    """

    def __init__(
        self,
        rds_client: Optional[RDSClient] = None,
        schema_inferrer: Optional[SchemaInferrer] = None,
        chunk_size: Optional[int] = None,
        skip_duplicates: bool = False,
        truncate_before_load: bool = False,
    ):
        """
        Initialize CSV ingestor with dependencies.

        Args:
            rds_client: Database client (creates new if None).
            schema_inferrer: Schema engine (creates new if None).
            chunk_size: Batch size (default: settings.csv_chunk_size).
            skip_duplicates: Skip duplicate key errors using INSERT IGNORE.
            truncate_before_load: Clear table before load.

        Side Effects:
            Creates client/inferrer instances if not provided and logs settings.
        """
        self.rds_client = rds_client or RDSClient()
        self.schema_inferrer = schema_inferrer or SchemaInferrer()
        self.chunk_size = int(chunk_size or settings.csv_chunk_size)
        self.skip_duplicates = bool(skip_duplicates)
        self.truncate_before_load = bool(truncate_before_load)

        logger.info(
            "Initialized CSVIngestor: chunk_size=%s, skip_duplicates=%s, truncate=%s",
            self.chunk_size,
            self.skip_duplicates,
            self.truncate_before_load,
        )

    # -------------------------------------------------------------------------
    # Helpers to normalize information_schema output (fixes your error)
    # -------------------------------------------------------------------------

    def _normalize_col_record(self, rec: dict) -> dict:
        """
        Normalize a single information_schema row to the keys expected by
        SchemaInferrer.compare_schemas: column_name, data_type, is_nullable,
        column_key, column_type. Missing keys are set to None.
        """
        # Lower all keys to be case-insensitive
        lower = {str(k).lower(): v for k, v in rec.items()}

        def get_any(d: dict, *candidates: str) -> Any:
            for k in candidates:
                if k in d:
                    return d[k]
            return None

        return {
            "column_name": get_any(lower, "column_name", "column", "name"),
            "data_type": get_any(lower, "data_type", "type"),
            "is_nullable": get_any(lower, "is_nullable", "nullable"),
            "column_key": get_any(lower, "column_key", "key"),
            "column_type": get_any(lower, "column_type", "full_type"),
        }

    def _normalize_existing_columns(self, existing_columns: Any) -> List[dict]:
        """
        Accept whatever shape RDSClient.get_table_columns returns and normalize to:
        list[dict] with keys -> column_name, data_type, is_nullable, column_key, column_type.
        """
        if existing_columns is None:
            return []

        # If a dict (single row), wrap as list
        if isinstance(existing_columns, dict):
            existing_columns = [existing_columns]

        normed: List[dict] = []
        for row in existing_columns:
            if isinstance(row, dict):
                normed.append(self._normalize_col_record(row))
            elif isinstance(row, (list, tuple)):
                # Fallback order: (COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, COLUMN_TYPE)
                cn, dt, nul, ck, ct = (row + (None, None, None, None, None))[:5]
                normed.append(
                    self._normalize_col_record(
                        {
                            "COLUMN_NAME": cn,
                            "DATA_TYPE": dt,
                            "IS_NULLABLE": nul,
                            "COLUMN_KEY": ck,
                            "COLUMN_TYPE": ct,
                        }
                    )
                )
            else:
                # Unknown row shape; skip but continue
                continue

        return normed

    # -------------------------------------------------------------------------
    # Schema operations
    # -------------------------------------------------------------------------

    def ensure_table_schema(
        self, schema: Dict[str, Any], update_if_exists: bool = True
    ) -> str:
        """
        Ensure table exists with correct schema (create or alter).

        Normalizes information_schema results from RDSClient.get_table_columns()
        so SchemaInferrer.compare_schemas() always receives the expected shape.

        Args:
            schema: Table schema from SchemaInferrer.infer_schema().
            update_if_exists: Add missing columns if table already exists.

        Returns:
            Final table name.

        Raises:
            DatabaseError: If DDL operations fail.
        """
        table_name = schema["table_name"]

        try:
            if not self.rds_client.table_exists(table_name):
                logger.info("Creating table: %s", table_name)
                self.rds_client.create_table(
                    table_name=table_name, columns=schema["columns"]
                )
                logger.info(
                    "Created table '%s' with %d columns",
                    table_name,
                    len(schema["columns"]),
                )

            elif update_if_exists:
                raw_existing = self.rds_client.get_table_columns(table_name)
                existing_columns = self._normalize_existing_columns(raw_existing)

                logger.debug(
                    "Existing columns (normalized) sample: %s",
                    existing_columns[:1] if existing_columns else "[]",
                )

                if not existing_columns:
                    # Treat as new (add all)
                    new_columns = schema["columns"]
                    compatible = True
                else:
                    new_columns, compatible = self.schema_inferrer.compare_schemas(
                        existing_columns, schema
                    )

                if not compatible:
                    logger.warning(
                        "Schema incompatibilities detected for '%s'—adding only new columns",
                        table_name,
                    )

                if new_columns:
                    logger.info(
                        "Adding %d new column(s) to '%s'",
                        len(new_columns),
                        table_name,
                    )
                    self.rds_client.add_columns(table_name, new_columns)
                else:
                    logger.info("Table '%s' schema is up to date", table_name)

            return table_name

        except KeyError as e:
            logger.error("Invalid existing columns structure (missing key): %s", e)
            raise DatabaseError(
                f"Schema structure mismatch: missing key {e!s}",
                details={
                    "table": table_name,
                    "expected_schema_keys": list(schema.keys()) if schema else None,
                },
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to ensure table schema: {str(e)}",
                details={"table": table_name, "error": str(e)},
            )

    # -------------------------------------------------------------------------
    # Insert helpers
    # -------------------------------------------------------------------------

    def _build_insert_query(self, table_name: str, normalized_cols: List[str]) -> str:
        """
        Build parameterized INSERT query for batch loading.

        Args:
            table_name: Target table.
            normalized_cols: Ordered list of column names in target table.

        Returns:
            MySQL INSERT string with %s placeholders.
        """
        placeholders = ", ".join(["%s"] * len(normalized_cols))
        columns_str = ", ".join(f"`{c}`" for c in normalized_cols)
        if self.skip_duplicates:
            return f"INSERT IGNORE INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"
        return f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"

    def _validate_column_mapping(
        self, frame_columns: List[str], column_mapping: Dict[str, str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that the frame contains all original columns needed.

        Returns:
            (ok, missing_columns)
        """
        needed = list(column_mapping.keys())
        missing = [c for c in needed if c not in frame_columns]
        ok = not missing
        if not ok:
            logger.error("Missing required columns in chunk: %s", missing)
        return ok, missing

    # -------------------------------------------------------------------------
    # Core load
    # -------------------------------------------------------------------------

    def load_csv_to_table(
        self, csv_path: Path, table_name: str, column_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Load CSV data into MySQL with streaming chunked inserts.

        Performance:
        - Restrict read to required columns via `usecols`.
        - Avoid Python row loops; vectorized NA→None conversion + values.tolist().
        - Build and reuse one INSERT statement for all chunks.

        Args:
            csv_path: CSV file.
            table_name: Target table.
            column_mapping: Dict[original_col -> normalized_col].

        Returns:
            Dict with attempted/loaded/failed counts, errors (capped), and timing.

        Raises:
            DataIngestionError: For top-level failures (I/O, DB, parsing).
        """
        start_time = datetime.now()
        rows_attempted = rows_loaded = 0
        errors: List[Dict[str, Any]] = []

        logger.info("Loading data from %s into '%s'", csv_path.name, table_name)

        try:
            if self.truncate_before_load:
                logger.info("Truncating table '%s' before load", table_name)
                self.rds_client.truncate_table(table_name)

            # Build INSERT once
            normalized_cols = list(column_mapping.values()) + [
                "ingestion_timestamp",
                "source_file",
            ]
            insert_query = self._build_insert_query(table_name, normalized_cols)

            # Metadata (constant per-file)
            ingestion_timestamp = datetime.now()
            source_file = csv_path.name

            # Only read the columns we need for better I/O perf
            usecols = list(column_mapping.keys())

            chunk_iter = pd.read_csv(
                csv_path,
                encoding=settings.csv_encoding,
                chunksize=self.chunk_size,
                usecols=usecols,
            )

            for chunk_idx, df_chunk in enumerate(chunk_iter, start=1):
                try:
                    ok, missing = self._validate_column_mapping(
                        df_chunk.columns.tolist(), column_mapping
                    )
                    if not ok:
                        failed_count = len(df_chunk)
                        errors.append(
                            {
                                "chunk": chunk_idx,
                                "error": "Required columns missing from chunk",
                                "missing_columns": missing,
                                "failed_rows": failed_count,
                            }
                        )
                        rows_attempted += failed_count
                        continue

                    # Reorder and replace NaN with None
                    df_sel = df_chunk[usecols].where(pd.notna(df_chunk[usecols]), None)

                    # Convert to python lists and append metadata
                    records = df_sel.values.tolist()
                    for rec in records:
                        rec.append(ingestion_timestamp)
                        rec.append(source_file)

                    batch_size = len(records)
                    rows_attempted += batch_size

                    if batch_size:
                        affected = self.rds_client.execute_many(
                            insert_query, [tuple(r) for r in records], commit=True
                        )
                        rows_loaded += affected
                        logger.info(
                            "Chunk %d: loaded %d/%d rows (total loaded=%d attempted=%d)",
                            chunk_idx,
                            affected,
                            batch_size,
                            rows_loaded,
                            rows_attempted,
                        )

                except DatabaseError as e:
                    # Whole chunk failed at DB level
                    failed_count = len(df_chunk)
                    errors.append(
                        {
                            "chunk": chunk_idx,
                            "error": e.message,
                            "details": e.details,
                            "failed_rows": failed_count,
                        }
                    )
                    rows_attempted += failed_count
                    logger.error("Chunk %d failed at DB level: %s", chunk_idx, e.message)

                except Exception as e:
                    failed_count = len(df_chunk)
                    errors.append(
                        {
                            "chunk": chunk_idx,
                            "error": f"Chunk preparation failed: {str(e)}",
                            "failed_rows": failed_count,
                        }
                    )
                    rows_attempted += failed_count
                    logger.error("Chunk %d preparation failed: %s", chunk_idx, str(e))

            duration = (datetime.now() - start_time).total_seconds()
            rows_failed = rows_attempted - rows_loaded
            result = {
                "table_name": table_name,
                "source_file": csv_path.name,
                "rows_attempted": rows_attempted,
                "rows_loaded": rows_loaded,
                "rows_failed": rows_failed,
                "errors": errors[:100],  # cap error list
                "duration_seconds": round(duration, 2),
                "success": rows_failed == 0,
            }

            logger.info(
                "Load complete: %d/%d rows loaded (%d failed) in %.2fs",
                rows_loaded,
                rows_attempted,
                rows_failed,
                duration,
            )
            return result

        except pd.errors.EmptyDataError:
            raise DataIngestionError(
                f"CSV file is empty or malformed: {csv_path}",
                details={"csv_path": str(csv_path), "table": table_name},
            )
        except pd.errors.ParserError as e:
            raise DataIngestionError(
                f"CSV parsing error: {str(e)}",
                details={"csv_path": str(csv_path), "table": table_name},
            )
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            raise DataIngestionError(
                f"Failed to load CSV data: {str(e)}",
                details={
                    "csv_path": str(csv_path),
                    "table": table_name,
                    "rows_attempted": rows_attempted,
                    "rows_loaded": rows_loaded,
                    "duration": duration,
                },
            )

    # -------------------------------------------------------------------------
    # Orchestration
    # -------------------------------------------------------------------------

    def ingest_csv(
        self, csv_path: Path, table_name: Optional[str] = None, update_schema: bool = True
    ) -> Dict[str, Any]:
        """
        Full pipeline: infer → create/update → load.

        Args:
            csv_path: CSV file to ingest.
            table_name: Optional target table override.
            update_schema: If True, add new columns to existing tables.

        Returns:
            Results with success flag, table name, and load statistics.

        Raises:
            FileDiscoveryError, SchemaInferenceError, DataIngestionError
        """
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
            final_table_name = self.ensure_table_schema(
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
            load_results = self.load_csv_to_table(
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

        except (SchemaInferenceError, DatabaseError, DataIngestionError) as e:
            logger.error("CSV ingestion failed: %s", e.message, extra={"details": e.details})
            raise
        except Exception as e:
            logger.error("Unexpected error during ingestion: %s", str(e))
            logger.debug(traceback.format_exc())
            raise DataIngestionError(
                f"CSV ingestion failed: {str(e)}",
                details={"csv_path": str(csv_path), "error": str(e)},
            )

    # -------------------------------------------------------------------------
    # Batch directory ingestion
    # -------------------------------------------------------------------------

    def ingest_directory(
        self, directory: Path, file_pattern: str = "*.csv", continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest all CSV files under a directory.

        Args:
            directory: Directory path.
            file_pattern: Glob for CSV selection.
            continue_on_error: Continue upon individual file failures.

        Returns:
            Batch summary with per-file results and errors.
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
                result = self.ingest_csv(csv_file)
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
            successful,
            len(csv_files),
            failed,
        )
        return batch_results
