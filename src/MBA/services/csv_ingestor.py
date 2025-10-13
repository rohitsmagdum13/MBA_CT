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

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import traceback

from MBA.core.exceptions import (
    DataIngestionError,
    SchemaInferenceError,
    DatabaseError,
    FileDiscoveryError
)
from MBA.core.logging_config import get_logger
from MBA.core.settings import settings
from MBA.services.rds_client import RDSClient
from MBA.services.schema_infer import SchemaInferrer

logger = get_logger(__name__)


class CSVIngestor:
    """
    CSV to MySQL ingestion orchestrator.
    
    Manages the complete pipeline for loading CSV data into MySQL including:
    - Schema inference and table creation/modification
    - Batch data loading with chunk processing
    - Row-level error handling and reporting
    - Metadata tracking (source file, ingestion timestamp)
    
    Attributes:
        rds_client (RDSClient): Database client instance
        schema_inferrer (SchemaInferrer): Schema inference engine
        chunk_size (int): Rows per batch insert
        skip_duplicates (bool): Skip duplicate rows on insert
        truncate_before_load (bool): Truncate table before loading
        
    Thread Safety:
        Not thread-safe. Create separate instances for concurrent use.
    """
    
    def __init__(
        self,
        rds_client: Optional[RDSClient] = None,
        schema_inferrer: Optional[SchemaInferrer] = None,
        chunk_size: Optional[int] = None,
        skip_duplicates: bool = False,
        truncate_before_load: bool = False
    ):
        """
        Initialize CSV ingestor with dependencies.
        
        Args:
            rds_client (Optional[RDSClient]): Database client (creates new if None)
            schema_inferrer (Optional[SchemaInferrer]): Schema engine (creates new if None)
            chunk_size (Optional[int]): Batch size (default: from settings)
            skip_duplicates (bool): Skip duplicate key errors (default: False)
            truncate_before_load (bool): Clear table before load (default: False)
            
        Side Effects:
            - Creates client instances if not provided
            - Logs initialization
        """
        self.rds_client = rds_client or RDSClient()
        self.schema_inferrer = schema_inferrer or SchemaInferrer()
        self.chunk_size = chunk_size or settings.csv_chunk_size
        self.skip_duplicates = skip_duplicates
        self.truncate_before_load = truncate_before_load
        
        logger.info(
            f"Initialized CSVIngestor: chunk_size={self.chunk_size}, "
            f"skip_duplicates={skip_duplicates}, truncate={truncate_before_load}"
        )
    
    def ensure_table_schema(
        self,
        schema: Dict[str, Any],
        update_if_exists: bool = True
    ) -> str:
        """
        Ensure table exists with correct schema.
        
        Creates table if it doesn't exist, or adds new columns if table
        exists and update_if_exists is True.
        
        Args:
            schema (Dict[str, Any]): Table schema from infer_schema
            update_if_exists (bool): Add missing columns to existing table
            
        Returns:
            str: Table name
            
        Raises:
            DatabaseError: If schema operations fail
            
        Side Effects:
            - May create new table
            - May alter existing table
            - Logs schema operations
        """
        table_name = schema['table_name']
        
        try:
            if not self.rds_client.table_exists(table_name):
                # Create new table
                logger.info(f"Creating table: {table_name}")
                
                self.rds_client.create_table(
                    table_name=table_name,
                    columns=schema['columns']
                )
                
                logger.info(
                    f"Created table '{table_name}' with {len(schema['columns'])} columns"
                )
            
            elif update_if_exists:
                # Check for new columns
                existing_columns = self.rds_client.get_table_columns(table_name)
                new_columns, compatible = self.schema_inferrer.compare_schemas(
                    existing_columns,
                    schema
                )
                
                if new_columns:
                    logger.info(
                        f"Adding {len(new_columns)} new columns to '{table_name}'"
                    )
                    self.rds_client.add_columns(table_name, new_columns)
                else:
                    logger.info(f"Table '{table_name}' schema is up to date")
            
            return table_name
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to ensure table schema: {str(e)}",
                details={"table": table_name, "error": str(e)}
            )
    
    def load_csv_to_table(
        self,
        csv_path: Path,
        table_name: str,
        column_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Load CSV data into MySQL table with batch processing.
        
        Reads CSV in chunks and inserts into database with error tracking
        and metadata addition.
        
        Args:
            csv_path (Path): CSV file to load
            table_name (str): Target table name
            column_mapping (Dict[str, str]): Original -> normalized column names
            
        Returns:
            Dict[str, Any]: Load statistics with keys:
                - rows_attempted (int): Total rows processed
                - rows_loaded (int): Successfully inserted rows
                - rows_failed (int): Failed insertions
                - errors (List[Dict]): Error details
                - duration_seconds (float): Processing time
                
        Raises:
            DataIngestionError: If loading fails completely
            
        Side Effects:
            - Inserts data into database
            - Logs progress and errors
        """
        start_time = datetime.now()
        rows_attempted = 0
        rows_loaded = 0
        rows_failed = 0
        errors = []
        
        logger.info(f"Loading data from {csv_path.name} into '{table_name}'")
        
        try:
            # Truncate if requested
            if self.truncate_before_load:
                logger.info(f"Truncating table '{table_name}'")
                self.rds_client.truncate_table(table_name)
            
            # Get column names for INSERT
            normalized_cols = list(column_mapping.values())
            normalized_cols.extend(['ingestion_timestamp', 'source_file'])
            
            # Build INSERT query
            placeholders = ', '.join(['%s'] * len(normalized_cols))
            columns_str = ', '.join([f'`{col}`' for col in normalized_cols])
            
            if self.skip_duplicates:
                insert_query = f"""
                    INSERT IGNORE INTO `{table_name}` ({columns_str})
                    VALUES ({placeholders})
                """
            else:
                insert_query = f"""
                    INSERT INTO `{table_name}` ({columns_str})
                    VALUES ({placeholders})
                """
            
            # Read and process CSV in chunks
            ingestion_timestamp = datetime.now()
            source_file = csv_path.name
            
            for chunk_idx, df_chunk in enumerate(
                pd.read_csv(
                    csv_path,
                    encoding=settings.csv_encoding,
                    chunksize=self.chunk_size
                ),
                start=1
            ):
                chunk_start = rows_attempted
                
                try:
                    # Prepare batch data
                    batch_data = []
                    
                    for idx, row in df_chunk.iterrows():
                        try:
                            # Map values to normalized column order
                            values = []
                            for orig_col, norm_col in column_mapping.items():
                                val = row[orig_col]
                                # Convert NaN to None for NULL
                                if pd.isna(val):
                                    values.append(None)
                                else:
                                    values.append(val)
                            
                            # Add metadata
                            values.append(ingestion_timestamp)
                            values.append(source_file)
                            
                            batch_data.append(tuple(values))
                            rows_attempted += 1
                            
                        except Exception as e:
                            rows_failed += 1
                            errors.append({
                                "row": int(idx) if not pd.isna(idx) else rows_attempted,
                                "error": f"Row preparation failed: {str(e)}"
                            })
                    
                    # Execute batch insert
                    if batch_data:
                        affected = self.rds_client.execute_many(
                            insert_query,
                            batch_data,
                            commit=True
                        )
                        rows_loaded += affected
                        
                        logger.info(
                            f"Chunk {chunk_idx}: loaded {affected}/{len(batch_data)} rows "
                            f"(total: {rows_loaded}/{rows_attempted})"
                        )
                
                except DatabaseError as e:
                    # Log chunk error but continue
                    chunk_size = rows_attempted - chunk_start
                    rows_failed += chunk_size
                    errors.append({
                        "chunk": chunk_idx,
                        "rows": f"{chunk_start}-{rows_attempted}",
                        "error": str(e)
                    })
                    logger.error(
                        f"Chunk {chunk_idx} failed: {e.message}",
                        extra={"details": e.details}
                    )
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Prepare results
            results = {
                "table_name": table_name,
                "source_file": csv_path.name,
                "rows_attempted": rows_attempted,
                "rows_loaded": rows_loaded,
                "rows_failed": rows_failed,
                "errors": errors[:100],  # Limit error list
                "duration_seconds": round(duration, 2),
                "success": rows_failed == 0
            }
            
            logger.info(
                f"Load complete: {rows_loaded}/{rows_attempted} rows loaded "
                f"({rows_failed} failed) in {duration:.2f}s"
            )
            
            return results
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            raise DataIngestionError(
                f"Failed to load CSV data: {str(e)}",
                details={
                    "csv_path": str(csv_path),
                    "table": table_name,
                    "rows_attempted": rows_attempted,
                    "rows_loaded": rows_loaded,
                    "duration": duration
                }
            )
    
    def ingest_csv(
        self,
        csv_path: Path,
        table_name: Optional[str] = None,
        update_schema: bool = True
    ) -> Dict[str, Any]:
        """
        Complete CSV ingestion pipeline: infer → create/update → load.
        
        Orchestrates the full ingestion process from schema inference
        through data loading.
        
        Args:
            csv_path (Path): CSV file to ingest
            table_name (Optional[str]): Target table (auto-generated if None)
            update_schema (bool): Update existing schema (default: True)
            
        Returns:
            Dict[str, Any]: Ingestion results with keys:
                - success (bool): Overall success status
                - table_name (str): Target table name
                - schema_created (bool): Whether new table was created
                - load_results (Dict): Data loading statistics
                
        Raises:
            FileDiscoveryError: If CSV doesn't exist
            SchemaInferenceError: If schema inference fails
            DataIngestionError: If loading fails
            
        Side Effects:
            - May create/alter table schema
            - Inserts data into database
            - Comprehensive logging
            
        Example:
            >>> ingestor = CSVIngestor()
            >>> results = ingestor.ingest_csv(Path("data/members.csv"))
            >>> print(f"Loaded {results['load_results']['rows_loaded']} rows")
        """
        if not csv_path.exists():
            raise FileDiscoveryError(
                f"CSV file not found: {csv_path}",
                details={"path": str(csv_path)}
            )
        
        logger.info(f"Starting CSV ingestion: {csv_path.name}")
        pipeline_start = datetime.now()
        
        try:
            # Step 1: Infer schema
            logger.info("Step 1/3: Inferring schema...")
            schema = self.schema_inferrer.infer_schema(
                csv_path,
                add_metadata_columns=True
            )
            
            # Override table name if provided
            if table_name:
                schema['table_name'] = table_name
            
            # Step 2: Ensure table exists with correct schema
            logger.info("Step 2/3: Ensuring table schema...")
            final_table_name = self.ensure_table_schema(
                schema,
                update_if_exists=update_schema
            )
            
            # Build column mapping (original -> normalized)
            column_mapping = {
                col['original_name']: col['name']
                for col in schema['columns']
                if col['original_name'] not in ['ingestion_timestamp', 'source_file']
            }
            
            # Step 3: Load data
            logger.info("Step 3/3: Loading data...")
            load_results = self.load_csv_to_table(
                csv_path,
                final_table_name,
                column_mapping
            )
            
            # Calculate total duration
            pipeline_duration = (datetime.now() - pipeline_start).total_seconds()
            
            # Prepare results
            results = {
                "success": load_results['success'],
                "csv_file": csv_path.name,
                "table_name": final_table_name,
                "columns_inferred": len(schema['columns']),
                "load_results": load_results,
                "pipeline_duration_seconds": round(pipeline_duration, 2)
            }
            
            if results['success']:
                logger.info(
                    f"✓ CSV ingestion successful: {csv_path.name} -> {final_table_name} "
                    f"({load_results['rows_loaded']} rows in {pipeline_duration:.2f}s)"
                )
            else:
                logger.warning(
                    f"⚠ CSV ingestion completed with errors: "
                    f"{load_results['rows_failed']} rows failed"
                )
            
            return results
            
        except (SchemaInferenceError, DatabaseError, DataIngestionError) as e:
            logger.error(
                f"CSV ingestion failed: {e.message}",
                extra={"details": e.details}
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error during ingestion: {str(e)}")
            logger.debug(traceback.format_exc())
            raise DataIngestionError(
                f"CSV ingestion failed: {str(e)}",
                details={"csv_path": str(csv_path), "error": str(e)}
            )
    
    def ingest_directory(
        self,
        directory: Path,
        file_pattern: str = "*.csv",
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest all CSV files in directory.
        
        Processes multiple CSV files with individual error handling
        and summary reporting.
        
        Args:
            directory (Path): Directory containing CSV files
            file_pattern (str): Glob pattern for files (default: "*.csv")
            continue_on_error (bool): Continue after individual failures
            
        Returns:
            Dict[str, Any]: Batch results with keys:
                - total_files (int): Number of files processed
                - successful (int): Successfully ingested files
                - failed (int): Failed ingestions
                - results (List[Dict]): Individual file results
                - errors (List[Dict]): Error details
                
        Example:
            >>> results = ingestor.ingest_directory(Path("data/csv"))
            >>> print(f"{results['successful']}/{results['total_files']} files loaded")
        """
        if not directory.exists():
            raise FileDiscoveryError(
                f"Directory not found: {directory}",
                details={"path": str(directory)}
            )
        
        if not directory.is_dir():
            raise FileDiscoveryError(
                f"Path is not a directory: {directory}",
                details={"path": str(directory)}
            )
        
        # Find CSV files
        csv_files = list(directory.glob(file_pattern))
        
        if not csv_files:
            logger.warning(f"No CSV files found in {directory}")
            return {
                "total_files": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
                "errors": []
            }
        
        logger.info(
            f"Starting batch ingestion: {len(csv_files)} files from {directory}"
        )
        
        successful = 0
        failed = 0
        results = []
        errors = []
        
        for idx, csv_file in enumerate(csv_files, 1):
            logger.info(f"Processing file {idx}/{len(csv_files)}: {csv_file.name}")
            
            try:
                result = self.ingest_csv(csv_file)
                results.append(result)
                
                if result['success']:
                    successful += 1
                else:
                    failed += 1
                
            except Exception as e:
                failed += 1
                error_info = {
                    "file": csv_file.name,
                    "error": str(e),
                    "type": type(e).__name__
                }
                errors.append(error_info)
                
                logger.error(f"Failed to ingest {csv_file.name}: {str(e)}")
                
                if not continue_on_error:
                    logger.error("Halting batch ingestion due to error")
                    break
        
        # Summary
        batch_results = {
            "total_files": len(csv_files),
            "successful": successful,
            "failed": failed,
            "results": results,
            "errors": errors
        }
        
        logger.info(
            f"Batch ingestion complete: {successful}/{len(csv_files)} successful, "
            f"{failed} failed"
        )
        
        return batch_results