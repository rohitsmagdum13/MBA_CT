"""
CSV data loading with chunked batch inserts.

Handles streaming CSV data into MySQL with error handling and metadata.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pandas as pd

from MBA.core.exceptions import DataIngestionError, DatabaseError
from MBA.core.logging_config import get_logger
from MBA.core.settings import settings
from MBA.services.database.client import RDSClient

logger = get_logger(__name__)


class CSVLoader:
    """Handles CSV data loading into MySQL tables."""

    def __init__(
        self,
        rds_client: Optional[RDSClient] = None,
        chunk_size: Optional[int] = None,
        skip_duplicates: bool = False,
        truncate_before_load: bool = False,
    ):
        self.rds_client = rds_client or RDSClient()
        self.chunk_size = int(chunk_size or settings.csv_chunk_size)
        self.skip_duplicates = bool(skip_duplicates)
        self.truncate_before_load = bool(truncate_before_load)

    def _build_insert_query(self, table_name: str, normalized_cols: List[str]) -> str:
        """Build parameterized INSERT query for batch loading."""
        placeholders = ", ".join(["%s"] * len(normalized_cols))
        columns_str = ", ".join(f"`{c}`" for c in normalized_cols)
        if self.skip_duplicates:
            return f"INSERT IGNORE INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"
        return f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"

    def _validate_column_mapping(
        self, frame_columns: List[str], column_mapping: Dict[str, str]
    ) -> Tuple[bool, List[str]]:
        """Validate that the frame contains all required columns."""
        needed = list(column_mapping.keys())
        missing = [c for c in needed if c not in frame_columns]
        ok = not missing
        if not ok:
            logger.error("Missing required columns in chunk: %s", missing)
        return ok, missing

    def load_csv_to_table(
        self, csv_path: Path, table_name: str, column_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Load CSV data into MySQL with streaming chunked inserts.
        
        Args:
            csv_path: CSV file
            table_name: Target table
            column_mapping: Dict[original_col -> normalized_col]
            
        Returns:
            Load statistics and errors
        """
        start_time = datetime.now()
        rows_attempted = rows_loaded = 0
        errors: List[Dict[str, Any]] = []

        logger.info("Loading data from %s into '%s'", csv_path.name, table_name)

        try:
            if self.truncate_before_load:
                logger.info("Truncating table '%s' before load", table_name)
                self.rds_client.truncate_table(table_name)

            normalized_cols = list(column_mapping.values()) + ["ingestion_timestamp", "source_file"]
            insert_query = self._build_insert_query(table_name, normalized_cols)

            ingestion_timestamp = datetime.now()
            source_file = csv_path.name
            usecols = list(column_mapping.keys())

            chunk_iter = pd.read_csv(
                csv_path,
                encoding=settings.csv_encoding,
                chunksize=self.chunk_size,
                usecols=usecols,
            )

            for chunk_idx, df_chunk in enumerate(chunk_iter, start=1):
                try:
                    ok, missing = self._validate_column_mapping(df_chunk.columns.tolist(), column_mapping)
                    if not ok:
                        failed_count = len(df_chunk)
                        errors.append({
                            "chunk": chunk_idx,
                            "error": "Required columns missing from chunk",
                            "missing_columns": missing,
                            "failed_rows": failed_count,
                        })
                        rows_attempted += failed_count
                        continue

                    df_sel = df_chunk[usecols].where(pd.notna(df_chunk[usecols]), None)
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
                            chunk_idx, affected, batch_size, rows_loaded, rows_attempted,
                        )

                except DatabaseError as e:
                    failed_count = len(df_chunk)
                    errors.append({
                        "chunk": chunk_idx,
                        "error": e.message,
                        "details": e.details,
                        "failed_rows": failed_count,
                    })
                    rows_attempted += failed_count
                    logger.error("Chunk %d failed at DB level: %s", chunk_idx, e.message)

                except Exception as e:
                    failed_count = len(df_chunk)
                    errors.append({
                        "chunk": chunk_idx,
                        "error": f"Chunk preparation failed: {str(e)}",
                        "failed_rows": failed_count,
                    })
                    rows_attempted += failed_count
                    logger.error("Chunk %d preparation failed: %s", chunk_idx, str(e))

            duration = (datetime.now() - start_time).total_seconds()
            rows_failed = rows_attempted - rows_loaded
            
            return {
                "table_name": table_name,
                "source_file": csv_path.name,
                "rows_attempted": rows_attempted,
                "rows_loaded": rows_loaded,
                "rows_failed": rows_failed,
                "errors": errors[:100],
                "duration_seconds": round(duration, 2),
                "success": rows_failed == 0,
            }

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