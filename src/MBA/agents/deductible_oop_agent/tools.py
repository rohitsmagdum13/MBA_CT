"""
Deductible and Out-of-Pocket (OOP) lookup tools for MBA workflows.

This module provides tools that interface with the RDS MySQL deductibles_oop
table to retrieve member deductible and OOP information for various plan types
and network levels (PPO, PAR, OON).

The tool supports:
- Member ID lookup
- Plan type filtering (Individual/Family)
- Network level filtering (PPO/PAR/OON)
- Deductible and OOP limit information
- Met amounts and remaining balances
- Dynamic SQL query construction
- Comprehensive error handling
"""

from typing import Dict, Any, Optional, List
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from strands import tool

from ...core.logging_config import get_logger

logger = get_logger(__name__)


def _parse_deductible_oop_results(member_id: str, results: List[tuple]) -> Dict[str, Any]:
    """
    Parse database results into structured deductible/OOP information.

    Transforms flat metric rows into hierarchical structure organized by
    plan type and network level.

    Args:
        member_id: Member identifier
        results: List of (metric, value) tuples from database

    Returns:
        Dictionary with structured deductible/OOP data

    Example:
        >>> results = [("Deductible IND PPO", "2683"), ("OOP IND PPO", "1120")]
        >>> _parse_deductible_oop_results("M1001", results)
        {
            "member_id": "M1001",
            "individual": {
                "ppo": {"deductible": 2683, "oop": 1120, ...},
                ...
            },
            ...
        }
    """
    data = {
        "member_id": member_id,
        "individual": {},
        "family": {}
    }

    # Convert results to dictionary for easier lookup
    metrics_dict = {metric: value for metric, value in results}

    # Parse individual plans
    for network in ["PPO", "PAR", "OON"]:
        network_key = network.lower()
        data["individual"][network_key] = {
            "deductible": metrics_dict.get(f"Deductible IND {network}"),
            "deductible_met": metrics_dict.get(f"Deductible IND {network} met"),
            "deductible_remaining": metrics_dict.get(f"Deductible IND {network} Remaining"),
            "oop": metrics_dict.get(f"OOP IND {network}"),
            "oop_met": metrics_dict.get(f"OOP IND {network} met"),
            "oop_remaining": metrics_dict.get(f"OOP IND {network} Remaining")
        }

    # Parse family plans
    for network in ["PPO", "PAR", "OON"]:
        network_key = network.lower()
        data["family"][network_key] = {
            "deductible": metrics_dict.get(f"Deductible FAM {network}"),
            "deductible_met": metrics_dict.get(f"Deductible FAM {network} met"),
            "deductible_remaining": metrics_dict.get(f"Deductible FAM {network} Remaining"),
            "oop": metrics_dict.get(f"OOP FAM {network}"),
            "oop_met": metrics_dict.get(f"OOP FAM {network} met"),
            "oop_remaining": metrics_dict.get(f"OOP FAM {network} Remaining")
        }

    return data


@tool
async def get_deductible_oop(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve deductible and out-of-pocket information for a member.

    Queries the deductibles_oop table to get comprehensive deductible and
    OOP limit information across all plan types and network levels. This tool
    integrates with AWS Bedrock via Strands orchestration.

    The data includes:
    - Deductible and OOP limits
    - Amounts met to date
    - Remaining balances
    - Individual and family plan types
    - PPO, PAR, and OON network levels

    Args:
        params: Dictionary containing:
            - member_id (str, required): Unique member identifier
            - plan_type (str, optional): "individual" or "family"
            - network (str, optional): "ppo", "par", or "oon"

    Returns:
        Dictionary containing deductible/OOP information:
        - Success: {
            "found": true,
            "member_id": str,
            "individual": {...},
            "family": {...}
          }
        - Not found: {"found": false, "message": "No data found for member"}
        - Missing member_id: {"found": false, "message": "member_id is required"}
        - Error: {"error": str}

    Raises:
        Does not raise exceptions - all errors returned as structured responses

    Example:
        >>> await get_deductible_oop({"member_id": "M1001"})
        {
            "found": true,
            "member_id": "M1001",
            "individual": {
                "ppo": {
                    "deductible": 2683,
                    "deductible_met": 1840,
                    "deductible_remaining": 843,
                    "oop": 1120,
                    "oop_met": 495,
                    "oop_remaining": 625
                },
                ...
            },
            "family": {...}
        }

    Database Schema:
        deductibles_oop table structure (transposed format):
        - Metric: VARCHAR (metric name like "Deductible IND PPO")
        - M1001, M1002, etc.: INTEGER (values for each member)
    """
    logger.info(f"Deductible/OOP lookup requested with parameters: {list(params.keys())}")
    logger.debug(f"Lookup params detail: {params}")

    # Validate member_id
    member_id = params.get("member_id")
    if not member_id:
        logger.warning("Deductible/OOP lookup attempted without member_id")
        return {
            "found": False,
            "message": "member_id is required"
        }

    member_id = str(member_id).strip()

    # Import database connection within function to avoid circular imports
    try:
        from ...etl.db import connect
    except ImportError as e:
        logger.error(f"Failed to import database connector: {e}")
        return {"error": "Lookup failed: Database module unavailable"}

    try:
        # Build query to get all metrics for the member
        # The table is in transposed format with member IDs as columns
        query_sql = f"""
            SELECT Metric, `{member_id}` as value
            FROM deductibles_oop
            WHERE `{member_id}` IS NOT NULL
        """

        logger.debug(f"Executing deductible/OOP query for member {member_id}")

        # Execute query
        try:
            with connect() as conn:
                logger.debug("Connected to database, executing query")
                results = conn.execute(text(query_sql)).fetchall()
                logger.debug(f"Database query executed successfully, got {len(results)} rows")
        except Exception as conn_error:
            logger.error(f"Database connection failed: {str(conn_error)}")
            raise

        # Process results
        if results and len(results) > 0:
            deductible_data = _parse_deductible_oop_results(member_id, results)
            deductible_data["found"] = True

            logger.info(
                f"Deductible/OOP lookup successful: {member_id}",
                extra={"member_id": member_id, "metrics_found": len(results)}
            )

            return deductible_data

        else:
            logger.warning(
                f"No deductible/OOP data found for member: {member_id}",
                extra={"member_id": member_id}
            )

            return {
                "found": False,
                "message": f"No deductible/OOP data found for member {member_id}"
            }

    except SQLAlchemyError as e:
        logger.error(
            f"Database error during deductible/OOP lookup: {str(e)}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        return {"error": f"Lookup failed: Database error"}

    except Exception as e:
        logger.error(
            f"Unexpected error during deductible/OOP lookup: {str(e)}",
            exc_info=True,
            extra={"error_type": type(e).__name__}
        )
        return {"error": f"Lookup failed: {str(e)}"}
