"""
High-level wrapper for Benefit Accumulator Lookup Agent.

This module provides a production-grade OOP interface to the Strands-based
benefit accumulator agent, encapsulating initialization, invocation, error handling,
and result processing.

The wrapper enables:
- Clean async interface for benefit accumulator workflows
- Structured exception handling with detailed error context
- Comprehensive logging for audit trails
- Type-safe parameter validation
- Graceful degradation on failures

Usage:
    agent = BenefitAccumulatorAgent()
    result = await agent.get_benefit_accumulator(member_id="M1001")
"""

from typing import Dict, Any, Optional

from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError, DatabaseError

logger = get_logger(__name__)


class BenefitAccumulatorAgent:
    """
    Production wrapper for AWS Bedrock-powered benefit accumulator lookup.

    Provides a clean async interface to the Strands agent orchestration
    layer, handling initialization, parameter validation, and result
    normalization for benefit usage inquiry workflows.

    This class integrates:
    - AWS Bedrock language models via boto3
    - RDS MySQL benefit accumulator database via SQLAlchemy
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
        Initialize Benefit Accumulator Agent wrapper.

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

        logger.info("BenefitAccumulatorAgent wrapper created")

    def _ensure_initialized(self):
        """
        Lazy initialization of underlying Strands agent.

        Loads the benefit accumulator agent on first use, enabling fast cold starts
        and reducing initialization overhead in testing environments.

        Raises:
            ConfigError: If agent cannot be initialized
            RuntimeError: If agent module import fails

        Side Effects:
            - Imports agent module
            - Initializes Bedrock client
            - Registers benefit accumulator tools
            - Sets _initialized flag
        """
        if self._initialized:
            return

        try:
            from .agent import benefit_accumulator_agent
            self._agent = benefit_accumulator_agent
            self._initialized = True

            logger.info("Benefit Accumulator Agent initialized on first use")

        except ImportError as e:
            logger.error(f"Failed to import benefit accumulator agent: {e}")
            raise RuntimeError(
                f"Agent initialization failed: Cannot import agent module - {str(e)}"
            )

        except ConfigError as e:
            logger.error(f"Agent configuration error: {e.message}", extra=e.details)
            raise

        except Exception as e:
            logger.error(f"Unexpected error initializing agent: {str(e)}")
            raise RuntimeError(f"Agent initialization failed: {str(e)}")

    def _build_lookup_prompt(self, params: Dict[str, Any]) -> str:
        """
        Build a natural language prompt for the Bedrock LLM.

        Args:
            params: Dictionary with member_id and optional service filter

        Returns:
            str: Formatted prompt for the agent
        """
        member_id = params.get("member_id")
        service = params.get("service")

        if service:
            prompt = f"Get benefit usage information for member {member_id} for service '{service}'. Use the get_benefit_accumulator tool to query the database."
        else:
            prompt = f"Get all benefit usage information for member {member_id}. Use the get_benefit_accumulator tool to query the database."

        return prompt

    def _parse_agent_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse the Strands agent response to extract lookup result.

        The agent response contains the tool execution results. We need to
        extract the structured data returned by the get_benefit_accumulator tool.

        Args:
            response: Response from agent.invoke_async()

        Returns:
            Dict[str, Any]: Benefit accumulator lookup result
        """
        try:
            # Strands agent returns a message object
            # Check if it has tool calls and results
            if hasattr(response, 'tool_calls') and response.tool_calls:
                # Get the last tool call result (get_benefit_accumulator)
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

    async def get_benefit_accumulator(
        self,
        member_id: str,
        service: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve benefit accumulator information for a member.

        Orchestrates the complete lookup workflow:
        1. Parameter validation
        2. Agent invocation via Strands
        3. Bedrock LLM reasoning
        4. Tool execution against RDS
        5. Response normalization

        Args:
            member_id: Unique member identifier (required)
            service: Filter by specific service name (optional)

        Returns:
            Dictionary containing benefit accumulator information:
            - Success: {"found": true, "member_id": str, "benefits": [...]}
            - Not Found: {"found": false, "message": str}
            - Error: {"error": str}

        Raises:
            ValueError: If member_id not provided
            RuntimeError: If agent execution fails

        Example:
            >>> agent = BenefitAccumulatorAgent()
            >>> result = await agent.get_benefit_accumulator(member_id="M1001")
            >>> print(result)
            {
                "found": true,
                "member_id": "M1001",
                "benefits": [
                    {"service": "Massage Therapy", "allowed_limit": "6 visit calendar year maximum", "used": 3, "remaining": 3},
                    ...
                ]
            }

        Side Effects:
            - Executes SQL queries against benefit_accumulator table
            - Logs lookup attempts and results
            - Initializes agent on first call
        """
        # Validate member_id
        if not member_id:
            logger.error("Benefit accumulator lookup attempted without member_id")
            raise ValueError("member_id is required")

        # Build parameters dictionary
        params = {"member_id": member_id}
        if service:
            params["service"] = service

        logger.info(
            f"Benefit accumulator lookup requested",
            extra={
                "member_id": member_id,
                "service": service,
                "params_provided": list(params.keys()),
                "param_count": len(params)
            }
        )

        # Ensure agent initialized
        try:
            self._ensure_initialized()
        except (ConfigError, RuntimeError) as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {"error": f"Lookup service unavailable: {str(e)}"}

        # Execute lookup via agent
        try:
            logger.info("=" * 60)
            logger.info("EXECUTING BENEFIT ACCUMULATOR LOOKUP WITH BEDROCK LLM")
            logger.info("=" * 60)
            logger.debug(f"Invoking benefit accumulator agent with params: {params}")

            # Build the user message for the agent
            user_message = self._build_lookup_prompt(params)
            logger.info(f"📤 Sending to Bedrock: {user_message}")

            # Invoke the Strands agent with Bedrock LLM
            # This is where the magic happens:
            # User Request → Strands Agent → AWS Bedrock LLM (Claude Sonnet 4.5)
            logger.info("🤖 Calling AWS Bedrock LLM via Strands Agent...")
            response = await self._agent.invoke_async(user_message)
            logger.info(f"📥 Bedrock LLM response received")
            logger.debug(f"Full response: {response}")

            # Extract the result from the agent response
            # Bedrock → get_benefit_accumulator Tool → RDS MySQL → Result
            result = self._parse_agent_response(response)

            logger.info(
                f"✅ Lookup completed via Bedrock",
                extra={
                    "success": result.get("found", False),
                    "has_error": "error" in result
                }
            )
            logger.info("=" * 60)

            return result

        except DatabaseError as e:
            logger.error(
                f"Database error during lookup: {e.message}",
                extra=e.details
            )
            return {"error": f"Lookup failed: Database error"}

        except Exception as e:
            logger.error(
                f"Agent execution failed: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )

            return {"error": f"Lookup failed: {str(e)}"}
