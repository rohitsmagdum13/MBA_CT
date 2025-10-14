"""
Schema management for MySQL tables.

Handles table creation, column addition, and schema validation.
"""

from typing import Dict, List, Optional, Any, Tuple
from MBA.core.exceptions import DatabaseError
from MBA.core.logging_config import get_logger
from MBA.services.database.client import RDSClient
from MBA.services.database.schema_inferrer import SchemaInferrer

logger = get_logger(__name__)


class SchemaManager:
    """Manages MySQL table schemas and DDL operations."""

    def __init__(self, rds_client: Optional[RDSClient] = None, schema_inferrer: Optional[SchemaInferrer] = None):
        self.rds_client = rds_client or RDSClient()
        self.schema_inferrer = schema_inferrer or SchemaInferrer()

    def _normalize_col_record(self, rec: dict) -> dict:
        """Normalize information_schema row to expected format."""
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
        """Normalize RDSClient.get_table_columns output to standard format."""
        if existing_columns is None:
            return []

        if isinstance(existing_columns, dict):
            existing_columns = [existing_columns]

        normed: List[dict] = []
        for row in existing_columns:
            if isinstance(row, dict):
                normed.append(self._normalize_col_record(row))
            elif isinstance(row, (list, tuple)):
                cn, dt, nul, ck, ct = (row + (None, None, None, None, None))[:5]
                normed.append(
                    self._normalize_col_record({
                        "COLUMN_NAME": cn,
                        "DATA_TYPE": dt,
                        "IS_NULLABLE": nul,
                        "COLUMN_KEY": ck,
                        "COLUMN_TYPE": ct,
                    })
                )
        return normed

    def ensure_table_schema(self, schema: Dict[str, Any], update_if_exists: bool = True) -> str:
        """
        Ensure table exists with correct schema.
        
        Args:
            schema: Table schema from SchemaInferrer
            update_if_exists: Add missing columns if table exists
            
        Returns:
            Final table name
        """
        table_name = schema["table_name"]

        try:
            if not self.rds_client.table_exists(table_name):
                logger.info("Creating table: %s", table_name)
                self.rds_client.create_table(table_name=table_name, columns=schema["columns"])
                logger.info("Created table '%s' with %d columns", table_name, len(schema["columns"]))

            elif update_if_exists:
                raw_existing = self.rds_client.get_table_columns(table_name)
                existing_columns = self._normalize_existing_columns(raw_existing)

                if not existing_columns:
                    new_columns = schema["columns"]
                    compatible = True
                else:
                    new_columns, compatible = self.schema_inferrer.compare_schemas(existing_columns, schema)

                if not compatible:
                    logger.warning("Schema incompatibilities detected for '%s'—adding only new columns", table_name)

                if new_columns:
                    logger.info("Adding %d new column(s) to '%s'", len(new_columns), table_name)
                    self.rds_client.add_columns(table_name, new_columns)
                else:
                    logger.info("Table '%s' schema is up to date", table_name)

            return table_name

        except KeyError as e:
            raise DatabaseError(
                f"Schema structure mismatch: missing key {e!s}",
                details={"table": table_name, "expected_schema_keys": list(schema.keys()) if schema else None},
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to ensure table schema: {str(e)}",
                details={"table": table_name, "error": str(e)},
            )