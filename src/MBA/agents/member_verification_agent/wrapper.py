"""
High-level wrapper for Member Verification Agent.

This module provides a production-grade OOP interface to the Strands-based
verification agent, encapsulating initialization, invocation, error handling,
and result processing.

The wrapper enables:
- Clean async interface for verification workflows
- Structured exception handling with detailed error context
- Comprehensive logging for audit trails
- Type-safe parameter validation
- Graceful degradation on failures

Usage:
    agent = MemberVerificationAgent()
    result = await agent.verify_member(member_id="M12345", dob="1990-01-01")
"""

from typing import Dict, Any, Optional
from datetime import date

from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError, DatabaseError

logger = get_logger(__name__)


class MemberVerificationAgent:
    """
    Production wrapper for AWS Bedrock-powered member verification.
    
    Provides a clean async interface to the Strands agent orchestration
    layer, handling initialization, parameter validation, and result
    normalization for member identity authentication workflows.
    
    This class integrates:
    - AWS Bedrock language models via boto3
    - RDS MySQL member database via SQLAlchemy
    - Strands agent orchestration framework
    - Structured logging and error handling
    
    Attributes:
        _agent: Underlying Strands Agent instance
        _initialized: Initialization state flag
        
    Thread Safety:
        Not thread-safe. Create separate instances per thread/task.
    """
    
    def __init__(self):
        """
        Initialize Member Verification Agent wrapper.
        
        Lazy-loads the Strands agent instance to defer Bedrock client
        initialization until first use. This pattern supports efficient
        Lambda cold starts and testing scenarios.
        
        Raises:
            ConfigError: If agent initialization fails due to missing
                credentials, invalid configuration, or service unavailability
                
        Side Effects:
            - Logs wrapper initialization
            - Defers agent initialization to first invocation
        """
        self._agent = None
        self._initialized = False
        
        logger.info("MemberVerificationAgent wrapper created")
    
    def _ensure_initialized(self):
        """
        Lazy initialization of underlying Strands agent.

        Loads the verification agent on first use, enabling fast cold starts
        and reducing initialization overhead in testing environments.

        Raises:
            ConfigError: If agent cannot be initialized
            RuntimeError: If agent module import fails

        Side Effects:
            - Imports agent module
            - Initializes Bedrock client
            - Registers verification tools
            - Sets _initialized flag
        """
        if self._initialized:
            return

        try:
            from .agent import verification_agent
            self._agent = verification_agent
            self._initialized = True

            logger.info("Member Verification Agent initialized on first use")

        except ImportError as e:
            logger.error(f"Failed to import verification agent: {e}")
            raise RuntimeError(
                f"Agent initialization failed: Cannot import agent module - {str(e)}"
            )

        except ConfigError as e:
            logger.error(f"Agent configuration error: {e.message}", extra=e.details)
            raise

        except Exception as e:
            logger.error(f"Unexpected error initializing agent: {str(e)}")
            raise RuntimeError(f"Agent initialization failed: {str(e)}")

    def _build_verification_prompt(self, params: Dict[str, Any]) -> str:
        """
        Build a natural language prompt for the Bedrock LLM.

        Args:
            params: Dictionary with member_id, dob, and/or name

        Returns:
            str: Formatted prompt for the agent
        """
        parts = []
        if params.get("member_id"):
            parts.append(f"member ID {params['member_id']}")
        if params.get("dob"):
            parts.append(f"date of birth {params['dob']}")
        if params.get("name"):
            parts.append(f"name {params['name']}")

        criteria = " and ".join(parts)
        return f"Verify the member with {criteria}. Use the verify_member tool to check the database."

    def _parse_agent_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse the Strands agent response to extract verification result.

        The agent response contains the tool execution results. We need to
        extract the structured data returned by the verify_member tool.

        Args:
            response: Response from agent.invoke_async()

        Returns:
            Dict[str, Any]: Verification result
        """
        try:
            # Strands agent returns a message object
            # Check if it has tool calls and results
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Get the last tool call result (verify_member)
                for tool_call in response.tool_calls:
                    if hasattr(tool_call, 'result'):
                        return tool_call.result

            # If no tool calls, check for content
            if hasattr(response, 'content'):
                import json
                # Try to parse JSON from content
                try:
                    return json.loads(response.content)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Fallback: return error
            logger.warning(f"Could not parse agent response: {response}")
            return {"error": "Failed to parse agent response"}

        except Exception as e:
            logger.error(f"Error parsing agent response: {str(e)}", exc_info=True)
            return {"error": f"Response parsing failed: {str(e)}"}
    
    async def verify_member(
        self,
        member_id: Optional[str] = None,
        dob: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify member identity using provided authentication parameters.
        
        Orchestrates the complete verification workflow:
        1. Parameter validation
        2. Agent invocation via Strands
        3. Bedrock LLM reasoning
        4. Tool execution against RDS
        5. Response normalization
        
        Args:
            member_id: Unique member identifier (optional)
            dob: Date of birth in YYYY-MM-DD format (optional)
            name: Member full name for secondary validation (optional)
            
        Returns:
            Dictionary containing verification results:
            - Success: {"valid": true, "member_id": str, "name": str, "dob": str}
            - Failure: {"valid": false, "message": str}
            - Error: {"error": str}
            
        Raises:
            ValueError: If no parameters provided
            RuntimeError: If agent execution fails
            
        Example:
            >>> agent = MemberVerificationAgent()
            >>> result = await agent.verify_member(
            ...     member_id="M12345",
            ...     dob="1990-01-01"
            ... )
            >>> print(result)
            {"valid": true, "member_id": "M12345", "name": "John Doe", ...}
            
        Side Effects:
            - Executes SQL queries against memberdata table
            - Logs verification attempts and results
            - Initializes agent on first call
        """
        # Validate at least one parameter provided
        if not any([member_id, dob, name]):
            logger.error("Verification attempted with no parameters")
            raise ValueError(
                "At least one verification parameter required: "
                "member_id, dob, or name"
            )
        
        # Build parameters dictionary
        params = {}
        if member_id:
            params["member_id"] = member_id
        if dob:
            params["dob"] = dob
        if name:
            params["name"] = name
        
        logger.info(
            f"Member verification requested",
            extra={
                "params_provided": list(params.keys()),
                "param_count": len(params)
            }
        )
        
        # Ensure agent initialized
        try:
            self._ensure_initialized()
        except (ConfigError, RuntimeError) as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {"error": f"Verification service unavailable: {str(e)}"}
        
        # Execute verification via agent
        try:
            logger.info("=" * 60)
            logger.info("EXECUTING VERIFICATION WITH BEDROCK LLM")
            logger.info("=" * 60)
            logger.debug(f"Invoking verification agent with params: {params}")

            # Build the user message for the agent
            user_message = self._build_verification_prompt(params)
            logger.info(f"📤 Sending to Bedrock: {user_message}")

            # Invoke the Strands agent with Bedrock LLM
            # This is where the magic happens:
            # User Request → Strands Agent → AWS Bedrock LLM (Claude Sonnet 4.5)
            logger.info("🤖 Calling AWS Bedrock LLM via Strands Agent...")
            response = await self._agent.invoke_async(user_message)
            logger.info(f"📥 Bedrock LLM response received")
            logger.debug(f"Full response: {response}")

            # Extract the result from the agent response
            # Bedrock → verify_member Tool → RDS MySQL → Result
            result = self._parse_agent_response(response)

            logger.info(
                f"✅ Verification completed via Bedrock",
                extra={
                    "success": result.get("valid", False),
                    "has_error": "error" in result
                }
            )
            logger.info("=" * 60)

            return result
        
        except DatabaseError as e:
            logger.error(
                f"Database error during verification: {e.message}",
                extra=e.details
            )
            return {"error": f"Verification failed: Database error"}
        
        except Exception as e:
            logger.error(
                f"Agent execution failed: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            
            return {"error": f"Verification failed: {str(e)}"}
    
    async def verify_member_batch(
        self,
        members: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        """
        Verify multiple members in batch operation.
        
        Processes a list of member verification requests independently,
        collecting results for all members. Continues processing on
        individual failures to maximize throughput.
        
        Args:
            members: List of parameter dictionaries, each containing
                member_id, dob, and/or name
                
        Returns:
            List of verification result dictionaries in same order as input
            
        Example:
            >>> results = await agent.verify_member_batch([
            ...     {"member_id": "M001", "dob": "1990-01-01"},
            ...     {"member_id": "M002", "dob": "1985-06-15"}
            ... ])
            
        Side Effects:
            - Executes multiple SQL queries
            - Logs batch processing progress
        """
        logger.info(f"Batch verification requested: {len(members)} members")
        
        results = []
        
        for idx, member_params in enumerate(members, 1):
            logger.debug(f"Processing member {idx}/{len(members)}")
            
            try:
                result = await self.verify_member(**member_params)
                results.append(result)
                
            except ValueError as e:
                logger.warning(f"Invalid parameters for member {idx}: {str(e)}")
                results.append({"error": f"Invalid parameters: {str(e)}"})
            
            except Exception as e:
                logger.error(f"Failed to verify member {idx}: {str(e)}")
                results.append({"error": f"Verification failed: {str(e)}"})
        
        logger.info(
            f"Batch verification complete: {len(results)} processed",
            extra={
                "successful": sum(1 for r in results if r.get("valid")),
                "failed": sum(1 for r in results if not r.get("valid") and "error" not in r),
                "errors": sum(1 for r in results if "error" in r)
            }
        )
        
        return results