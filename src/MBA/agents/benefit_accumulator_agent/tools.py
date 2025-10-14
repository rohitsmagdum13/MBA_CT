"""
Benefit accumulator lookup tools for MBA workflows.

This module provides tools that interface with the RDS MySQL benefit_accumulator
table to retrieve member benefit usage information for various healthcare services.

The tool supports:
- Member ID lookup
- Service-specific benefit queries
- Allowed limits per service
- Used amounts tracking
- Remaining benefit balances
- Dynamic SQL query construction
- Comprehensive error handling
"""

from typing import Dict, Any, Optional, List
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from strands import tool

from ...core.logging_config import get_logger

logger = get_logger(__name__)


def _format_benefit_results(results: List[tuple]) -> List[Dict[str, Any]]:
    """
    Format database results into structured benefit information.

    Args:
        results: List of (service, allowed_limit, used, remaining) tuples

    Returns:
        List of dictionaries with service benefit details

    Example:
        >>> results = [("Massage Therapy", "6 visit calendar year maximum", 3, 3)]
        >>> _format_benefit_results(results)
        [{"service": "Massage Therapy", "allowed_limit": "6 visit calendar year maximum", ...}]
    """
    benefits = []
    for row in results:
        benefits.append({
            "service": row[0],
            "allowed_limit": row[1],
            "used": row[2],
            "remaining": row[3]
        })
    return benefits


@tool
async def get_benefit_accumulator(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve benefit accumulator information for a member.

    Queries the benefit_accumulator table to get comprehensive benefit usage
    information across all services. This tool integrates with AWS Bedrock
    via Strands orchestration.

    The data includes:
    - Service names (e.g., "Massage Therapy", "Skilled Nursing Facility")
    - Allowed limits with time period (e.g., "6 visit calendar year maximum")
    - Amount used to date
    - Remaining balance

    Args:
        params: Dictionary containing:
            - member_id (str, required): Unique member identifier
            - service (str, optional): Specific service name to filter

    Returns:
        Dictionary containing benefit accumulator information:
        - Success: {
            "found": true,
            "member_id": str,
            "benefits": [
                {
                    "service": str,
                    "allowed_limit": str,
                    "used": int,
                    "remaining": int
                },
                ...
            ]
          }
        - Not found: {"found": false, "message": "No benefits found for member"}
        - Missing member_id: {"found": false, "message": "member_id is required"}
        - Error: {"error": str}

    Raises:
        Does not raise exceptions - all errors returned as structured responses

    Example:
        >>> await get_benefit_accumulator({"member_id": "M1001"})
        {
            "found": true,
            "member_id": "M1001",
            "benefits": [
                {
                    "service": "Massage Therapy",
                    "allowed_limit": "6 visit calendar year maximum",
                    "used": 3,
                    "remaining": 3
                },
                {
                    "service": "Neurodevelopmental Therapy",
                    "allowed_limit": "30 visit calendar year maximum",
                    "used": 2,
                    "remaining": 28
                }
            ]
        }

        >>> await get_benefit_accumulator({"member_id": "M1001", "service": "Massage Therapy"})
        {
            "found": true,
            "member_id": "M1001",
            "benefits": [
                {
                    "service": "Massage Therapy",
                    "allowed_limit": "6 visit calendar year maximum",
                    "used": 3,
                    "remaining": 3
                }
            ]
        }

    Database Schema:
        benefit_accumulator table must contain:
        - member_id: VARCHAR (member identifier)
        - service: VARCHAR (service name)
        - allowed_limit: VARCHAR (limit description)
        - used: INTEGER (amount used)
        - remaining: INTEGER (amount remaining)
    """
    logger.info(f"Benefit accumulator lookup requested with parameters: {list(params.keys())}")
    logger.debug(f"Lookup params detail: {params}")

    # Validate member_id
    member_id = params.get("member_id")
    if not member_id:
        logger.warning("Benefit accumulator lookup attempted without member_id")
        return {
            "found": False,
            "message": "member_id is required"
        }

    member_id = str(member_id).strip()
    service = params.get("service")

    # Import database connection within function to avoid circular imports
    try:
        from ...etl.db import connect
    except ImportError as e:
        logger.error(f"Failed to import database connector: {e}")
        return {"error": "Lookup failed: Database module unavailable"}

    try:
        # Build query (using DISTINCT to handle duplicate records in database)
        if service:
            service = str(service).strip()
            query_sql = """
                SELECT DISTINCT service, allowed_limit, used, remaining
                FROM benefit_accumulator
                WHERE member_id = :member_id AND service = :service
                ORDER BY service
            """
            sql_params = {"member_id": member_id, "service": service}
            logger.debug(f"Executing benefit lookup for member {member_id}, service {service}")
        else:
            query_sql = """
                SELECT DISTINCT service, allowed_limit, used, remaining
                FROM benefit_accumulator
                WHERE member_id = :member_id
                ORDER BY service
            """
            sql_params = {"member_id": member_id}
            logger.debug(f"Executing benefit lookup for member {member_id}, all services")

        # Execute query
        try:
            with connect() as conn:
                logger.debug("Connected to database, executing query")
                results = conn.execute(text(query_sql), sql_params).fetchall()
                logger.debug(f"Database query executed successfully, got {len(results)} rows")
        except Exception as conn_error:
            logger.error(f"Database connection failed: {str(conn_error)}")
            raise

        # Process results
        if results and len(results) > 0:
            benefits = _format_benefit_results(results)

            response = {
                "found": True,
                "member_id": member_id,
                "benefits": benefits
            }

            logger.info(
                f"Benefit accumulator lookup successful: {member_id}",
                extra={"member_id": member_id, "benefits_found": len(benefits)}
            )

            return response

        else:
            logger.warning(
                f"No benefit accumulator data found for member: {member_id}",
                extra={"member_id": member_id, "service": service}
            )

            return {
                "found": False,
                "message": f"No benefits found for member {member_id}"
            }

    except SQLAlchemyError as e:
        logger.error(
            f"Database error during benefit accumulator lookup: {str(e)}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        return {"error": f"Lookup failed: Database error"}

    except Exception as e:
        logger.error(
            f"Unexpected error during benefit accumulator lookup: {str(e)}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        return {"error": f"Lookup failed: {str(e)}"}
