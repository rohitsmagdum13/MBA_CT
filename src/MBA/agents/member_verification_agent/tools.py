"""
Member verification tools for MBA authentication workflows.

This module provides the core verification tool that interfaces with the
RDS MySQL memberdata table to validate member identities using flexible
criteria combinations.

The tool supports:
- Member ID verification
- Date of birth matching
- Name validation (optional)
- Dynamic SQL query construction
- Comprehensive error handling
"""

from typing import Dict, Any, Optional
from datetime import date
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from strands import tool

from ...core.logging_config import get_logger

logger = get_logger(__name__)


def _build_verification_query(params: Dict[str, Any]) -> tuple[Optional[str], Dict[str, Any]]:
    """
    Construct dynamic SQL query based on provided parameters.

    Builds WHERE clause conditions using AND logic for multi-parameter
    verification. Validates parameter presence and formats SQL safely.

    Args:
        params: Dictionary containing member_id, dob, and/or name

    Returns:
        Tuple of (SQL query string, parameter dict) or (None, empty dict)
        if no valid parameters provided

    Example:
        >>> _build_verification_query({"member_id": "M123", "dob": "1990-01-01"})
        ('SELECT ... WHERE member_id = :member_id AND dob = :dob', {...})
    """
    conditions = []
    sql_params = {}

    # Member ID condition
    if params.get("member_id"):
        conditions.append("member_id = :member_id")
        sql_params["member_id"] = str(params["member_id"]).strip()

    # Date of birth condition
    if params.get("dob"):
        conditions.append("dob = :dob")
        dob_value = params["dob"]

        # Handle date objects or string dates
        if isinstance(dob_value, date):
            sql_params["dob"] = dob_value
        else:
            sql_params["dob"] = str(dob_value).strip()

    # Name condition (optional secondary validation)
    if params.get("name"):
        conditions.append(
            "(CONCAT(first_name, ' ', last_name) = :name OR "
            "first_name = :first_name OR last_name = :last_name)"
        )
        try:
            name_parts = str(params["name"]).strip().split(maxsplit=1)
            sql_params["name"] = params["name"]
            sql_params["first_name"] = name_parts[0] if name_parts else ""
            sql_params["last_name"] = name_parts[1] if len(name_parts) > 1 else (name_parts[0] if name_parts else "")
        except (AttributeError, IndexError):
            sql_params["name"] = str(params["name"])
            sql_params["first_name"] = ""
            sql_params["last_name"] = ""

    # No valid conditions
    if not conditions:
        return None, {}

    # Construct query with AND logic for stricter validation
    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT
            member_id,
            CONCAT(first_name, ' ', last_name) AS name,
            dob
        FROM memberdata
        WHERE {where_clause}
        LIMIT 1
    """

    return query, sql_params


@tool
async def verify_member(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify member identity using flexible authentication criteria.

    Authenticates members by querying the memberdata table with provided
    identifiers. Supports single or multi-parameter verification with
    AND logic for enhanced security.

    This tool integrates with AWS Bedrock via Strands orchestration and
    provides structured JSON responses for downstream processing.

    Args:
        params: Dictionary containing one or more of:
            - member_id (str): Unique member identifier
            - dob (str|date): Date of birth in YYYY-MM-DD format
            - name (str, optional): Full name for secondary validation

    Returns:
        Dictionary containing verification results:
        - Success: {"valid": true, "member_id": str, "name": str, "dob": str}
        - Failure: {"valid": false, "message": "Authentication failed"}
        - Missing params: {"valid": false, "message": "At least one identifier required"}
        - Error: {"error": str}

    Raises:
        Does not raise exceptions - all errors returned as structured responses

    Example:
        >>> await verify_member({"member_id": "M12345", "dob": "1985-06-15"})
        {"valid": true, "member_id": "M12345", "name": "John Doe", "dob": "1985-06-15"}

        >>> await verify_member({"member_id": "INVALID"})
        {"valid": false, "message": "Authentication failed"}

    Database Schema:
        memberdata table must contain:
        - member_id: VARCHAR (primary identifier)
        - first_name: VARCHAR
        - last_name: VARCHAR
        - dob: DATE
    """
    logger.info(f"Member verification requested with parameters: {list(params.keys())}")
    logger.debug(f"Verification params detail: {params}")

    # Import database connection within function to avoid circular imports
    try:
        from ...etl.db import connect
    except ImportError as e:
        logger.error(f"Failed to import database connector: {e}")
        return {"error": "Verification failed: Database module unavailable"}

    try:
        # Build dynamic query
        query_sql, sql_params = _build_verification_query(params)

        if query_sql is None:
            logger.warning("Verification attempted with no valid parameters")
            return {
                "valid": False,
                "message": "At least one identifier required"
            }

        logger.debug(f"Executing verification query with {len(sql_params)} parameters")
        logger.debug(f"Query: {query_sql[:100]}...")

        # Execute query
        logger.debug("Establishing database connection for verification")
        try:
            with connect() as conn:
                logger.debug(f"Connected to database, executing query")
                result = conn.execute(text(query_sql), sql_params).fetchone()
                logger.debug("Database query executed successfully")
        except Exception as conn_error:
            logger.error(f"Database connection failed: {str(conn_error)}")
            raise

        # Process results
        if result:
            try:
                dob_str = str(result.dob) if result.dob is not None else ""
            except (AttributeError, TypeError):
                dob_str = ""

            member_data = {
                "valid": True,
                "member_id": result.member_id,
                "name": result.name,
                "dob": dob_str
            }

            logger.info(
                f"Member verification successful: {result.member_id}",
                extra={"member_id": result.member_id}
            )

            return member_data

        else:
            logger.warning(
                "Member verification failed: No matching record",
                extra={"params_provided": list(params.keys())}
            )

            return {
                "valid": False,
                "message": "Authentication failed"
            }

    except SQLAlchemyError as e:
        logger.error(
            f"Database error during member verification: {str(e)}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        return {"error": f"Verification failed: Database error"}

    except Exception as e:
        logger.error(
            f"Unexpected error during member verification: {str(e)}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        return {"error": f"Verification failed: {str(e)}"}
