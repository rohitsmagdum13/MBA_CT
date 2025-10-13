"""
CSV schema inference for automatic MySQL table creation.

This module provides the SchemaInferrer class for analyzing CSV files and
generating appropriate MySQL table schemas with type inference, column naming
normalization, and validation.

Module Input:
    - CSV file paths
    - Pandas DataFrames from parsed CSVs
    - Column data samples for type detection

Module Output:
    - MySQL table schemas with column definitions
    - Normalized table and column names
    - Data type mappings and constraints
"""

import pandas as pd
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from MBA.core.exceptions import SchemaInferenceError, FileDiscoveryError
from MBA.core.logging_config import get_logger
from MBA.core.settings import settings

logger = get_logger(__name__)


class SchemaInferrer:
    """
    CSV schema inference engine for MySQL table generation.
    
    Analyzes CSV files to automatically determine appropriate MySQL column
    types, generates normalized table/column names, and creates DDL-ready
    schema definitions.
    
    Uses pandas for CSV parsing and implements intelligent type detection
    based on data sampling and pattern matching.
    
    Attributes:
        sample_rows (int): Number of rows to sample for type inference
        max_varchar_length (int): Maximum VARCHAR length (default: 500)
        use_text_threshold (int): Use TEXT type above this length
        
    Thread Safety:
        Thread-safe for read operations. Instance methods are stateless.
    """
    
    def __init__(
        self,
        sample_rows: int = 1000,
        max_varchar_length: int = 500,
        use_text_threshold: int = 1000
    ):
        """
        Initialize schema inferrer with configuration.
        
        Args:
            sample_rows (int): Rows to sample for type detection (default: 1000)
            max_varchar_length (int): Max VARCHAR size (default: 500)
            use_text_threshold (int): Switch to TEXT above length (default: 1000)
            
        Side Effects:
            - Logs initialization
        """
        self.sample_rows = sample_rows
        self.max_varchar_length = max_varchar_length
        self.use_text_threshold = use_text_threshold
        
        logger.info(
            f"Initialized SchemaInferrer: sample_rows={sample_rows}, "
            f"max_varchar={max_varchar_length}"
        )
    
    def normalize_table_name(self, file_path: Path) -> str:
        """
        Generate normalized table name from CSV filename.
        
        Converts filename to valid MySQL identifier by:
        - Removing file extension
        - Converting to lowercase
        - Replacing invalid characters with underscores
        - Ensuring starts with letter or underscore
        
        Args:
            file_path (Path): CSV file path
            
        Returns:
            str: Valid MySQL table name
            
        Example:
            >>> inferrer.normalize_table_name(Path("Member Data-2024.csv"))
            'member_data_2024'
        """
        # Get filename without extension
        name = file_path.stem
        
        # Convert to lowercase
        name = name.lower()
        
        # Replace spaces and special chars with underscores
        name = re.sub(r'[^\w]+', '_', name)
        
        # Remove leading/trailing underscores
        name = name.strip('_')
        
        # Ensure starts with letter or underscore
        if name and name[0].isdigit():
            name = f"tbl_{name}"
        
        # Limit length
        if len(name) > 64:
            name = name[:64]
        
        logger.debug(f"Normalized table name: {file_path.name} -> {name}")
        
        return name
    
    def normalize_column_name(self, column: str) -> str:
        """
        Normalize column name to valid MySQL identifier.
        
        Args:
            column (str): Original column name
            
        Returns:
            str: Valid MySQL column name
            
        Example:
            >>> inferrer.normalize_column_name("Member ID#")
            'member_id'
        """
        # Convert to lowercase
        name = column.lower()
        
        # Replace special chars with underscores
        name = re.sub(r'[^\w]+', '_', name)
        
        # Remove leading/trailing underscores
        name = name.strip('_')
        
        # Ensure not empty
        if not name:
            name = "col"
        
        # Ensure starts with letter or underscore
        if name[0].isdigit():
            name = f"col_{name}"
        
        # Limit length
        if len(name) > 64:
            name = name[:64]
        
        return name
    
    def infer_column_type(
        self,
        series: pd.Series,
        column_name: str
    ) -> Dict[str, Any]:
        """
        Infer MySQL column type from pandas Series.
        
        Analyzes data samples to determine appropriate MySQL type
        with size constraints and nullability.
        
        Args:
            series (pd.Series): Column data for analysis
            column_name (str): Column name for logging
            
        Returns:
            Dict[str, Any]: Column definition with keys:
                - name (str): Normalized column name
                - type (str): MySQL data type
                - nullable (bool): Allow NULL values
                - original_name (str): Original column name
                
        Example:
            >>> df = pd.read_csv("data.csv")
            >>> col_def = inferrer.infer_column_type(df['age'], 'age')
            >>> print(col_def)
            {'name': 'age', 'type': 'INT', 'nullable': True, 'original_name': 'age'}
        """
        normalized_name = self.normalize_column_name(column_name)
        
        # Check if column is entirely null
        if series.isna().all():
            return {
                "name": normalized_name,
                "type": "TEXT",
                "nullable": True,
                "original_name": column_name
            }
        
        # Sample non-null values
        non_null = series.dropna()
        
        # Check for boolean
        if series.dtype == bool or non_null.isin([0, 1, True, False]).all():
            return {
                "name": normalized_name,
                "type": "BOOLEAN",
                "nullable": series.isna().any(),
                "original_name": column_name
            }
        
        # Check for integers
        if pd.api.types.is_integer_dtype(series):
            max_val = non_null.max()
            min_val = non_null.min()
            
            # Choose appropriate integer type
            if min_val >= 0 and max_val < 256:
                col_type = "TINYINT UNSIGNED"
            elif min_val >= -128 and max_val < 128:
                col_type = "TINYINT"
            elif min_val >= 0 and max_val < 65536:
                col_type = "SMALLINT UNSIGNED"
            elif min_val >= -32768 and max_val < 32768:
                col_type = "SMALLINT"
            elif min_val >= 0 and max_val < 4294967296:
                col_type = "INT UNSIGNED"
            elif min_val >= -2147483648 and max_val < 2147483648:
                col_type = "INT"
            else:
                col_type = "BIGINT"
            
            return {
                "name": normalized_name,
                "type": col_type,
                "nullable": series.isna().any(),
                "original_name": column_name
            }
        
        # Check for floats
        if pd.api.types.is_float_dtype(series):
            return {
                "name": normalized_name,
                "type": "DOUBLE",
                "nullable": series.isna().any(),
                "original_name": column_name
            }
        
        # Check for datetime
        if pd.api.types.is_datetime64_any_dtype(series):
            return {
                "name": normalized_name,
                "type": "DATETIME",
                "nullable": series.isna().any(),
                "original_name": column_name
            }
        
        # Try to parse as datetime
        try:
            pd.to_datetime(non_null.head(100), errors='coerce')
            parsed_count = pd.to_datetime(non_null.head(100), errors='coerce').notna().sum()
            if parsed_count > 50:  # More than 50% are valid dates
                return {
                    "name": normalized_name,
                    "type": "DATETIME",
                    "nullable": series.isna().any(),
                    "original_name": column_name
                }
        except:
            pass
        
        # Default to string type - check max length
        max_length = non_null.astype(str).str.len().max()
        
        if pd.isna(max_length):
            max_length = 0
        
        if max_length > self.use_text_threshold:
            col_type = "TEXT"
        elif max_length > self.max_varchar_length:
            col_type = f"VARCHAR({self.max_varchar_length})"
        else:
            # Use next power of 2 or common sizes
            if max_length <= 50:
                col_type = "VARCHAR(50)"
            elif max_length <= 100:
                col_type = "VARCHAR(100)"
            elif max_length <= 255:
                col_type = "VARCHAR(255)"
            else:
                col_type = f"VARCHAR({self.max_varchar_length})"
        
        return {
            "name": normalized_name,
            "type": col_type,
            "nullable": series.isna().any(),
            "original_name": column_name
        }
    
    def infer_schema(
        self,
        csv_path: Path,
        add_metadata_columns: bool = True
    ) -> Dict[str, Any]:
        """
        Infer complete table schema from CSV file.
        
        Reads CSV, analyzes columns, and generates MySQL-ready schema
        with normalized names and appropriate types.
        
        Args:
            csv_path (Path): Path to CSV file
            add_metadata_columns (bool): Add created_at/updated_at (default: True)
            
        Returns:
            Dict[str, Any]: Schema definition with keys:
                - table_name (str): Normalized table name
                - columns (List[Dict]): Column definitions
                - row_count (int): Number of rows in CSV
                - has_header (bool): Whether CSV has header row
                
        Raises:
            FileDiscoveryError: If CSV cannot be read
            SchemaInferenceError: If schema inference fails
            
        Side Effects:
            - Reads CSV file
            - Logs schema inference progress
            
        Example:
            >>> schema = inferrer.infer_schema(Path("data/members.csv"))
            >>> print(f"Table: {schema['table_name']}")
            >>> for col in schema['columns']:
            ...     print(f"  {col['name']}: {col['type']}")
        """
        if not csv_path.exists():
            raise FileDiscoveryError(
                f"CSV file not found: {csv_path}",
                details={"path": str(csv_path)}
            )
        
        logger.info(f"Inferring schema from: {csv_path.name}")
        
        try:
            # Read CSV with pandas
            df = pd.read_csv(
                csv_path,
                encoding=settings.csv_encoding,
                nrows=self.sample_rows
            )
            
            if df.empty:
                raise SchemaInferenceError(
                    f"CSV file is empty: {csv_path}",
                    details={"path": str(csv_path)}
                )
            
            # Generate table name
            table_name = self.normalize_table_name(csv_path)
            
            # Infer column types
            columns = []
            for col in df.columns:
                col_def = self.infer_column_type(df[col], col)
                columns.append(col_def)
                logger.debug(
                    f"Column '{col}' -> {col_def['name']}: {col_def['type']}"
                )
            
            # Add metadata columns if requested
            if add_metadata_columns:
                columns.extend([
                    {
                        "name": "ingestion_timestamp",
                        "type": "TIMESTAMP",
                        "nullable": False,
                        "original_name": "ingestion_timestamp"
                    },
                    {
                        "name": "source_file",
                        "type": "VARCHAR(255)",
                        "nullable": True,
                        "original_name": "source_file"
                    }
                ])
            
            # Get actual row count
            row_count = len(df)
            
            schema = {
                "table_name": table_name,
                "columns": columns,
                "row_count": row_count,
                "has_header": True,
                "source_file": csv_path.name
            }
            
            logger.info(
                f"Inferred schema for '{table_name}': "
                f"{len(columns)} columns, {row_count} sample rows"
            )
            
            return schema
            
        except pd.errors.EmptyDataError:
            raise SchemaInferenceError(
                f"CSV file is empty or malformed: {csv_path}",
                details={"path": str(csv_path)}
            )
        except pd.errors.ParserError as e:
            raise SchemaInferenceError(
                f"Failed to parse CSV: {str(e)}",
                details={"path": str(csv_path), "error": str(e)}
            )
        except Exception as e:
            raise SchemaInferenceError(
                f"Schema inference failed: {str(e)}",
                details={"path": str(csv_path), "error": str(e)}
            )
    
    def compare_schemas(
        self,
        existing_columns: List[Dict[str, Any]],
        new_schema: Dict[str, Any]
    ) -> Tuple[List[Dict], bool]:
        """
        Compare existing table schema with inferred schema.
        
        Identifies new columns that need to be added to existing table.
        
        Args:
            existing_columns (List[Dict[str, Any]]): Current table columns
            new_schema (Dict[str, Any]): Newly inferred schema
            
        Returns:
            Tuple[List[Dict], bool]: 
                - List of new columns to add
                - Whether schema is compatible (no conflicts)
                
        Example:
            >>> existing = [{"column_name": "id", "data_type": "int"}]
            >>> new_schema = inferrer.infer_schema(Path("updated.csv"))
            >>> new_cols, compatible = inferrer.compare_schemas(existing, new_schema)
        """
        # Handle empty existing columns list
        if not existing_columns:
            logger.info("No existing columns found - all columns are new")
            return new_schema['columns'], True
            
        # Validate existing columns structure
        if existing_columns and 'column_name' not in existing_columns[0]:
            logger.error(f"Invalid existing columns structure: {existing_columns[0].keys() if existing_columns else 'empty'}")
            raise ValueError(f"Expected 'column_name' key in existing columns, got: {list(existing_columns[0].keys()) if existing_columns else 'empty list'}")
            
        existing_names = {col['column_name'].lower() for col in existing_columns}
        
        new_columns = []
        compatible = True
        
        for col in new_schema['columns']:
            if col['name'].lower() not in existing_names:
                new_columns.append(col)
                logger.info(f"New column detected: {col['name']} ({col['type']})")
        
        if new_columns:
            logger.info(
                f"Schema comparison: {len(new_columns)} new columns need to be added"
            )
        else:
            logger.info("Schema comparison: no new columns needed")
        
        return new_columns, compatible