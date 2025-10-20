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
from ...core.exceptions import ConfigError, DatabaseError, AgentError, ValidationError

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
            AgentError: If agent module import fails

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
            raise AgentError(
                f"Agent initialization failed: Cannot import agent module - {str(e)}",
                details={"agent_type": "benefit_accumulator", "error_type": "ImportError"}
            )

        except ConfigError as e:
            logger.error(f"Agent configuration error: {e.message}", extra=e.details)
            raise

        except Exception as e:
            logger.error(f"Unexpected error initializing agent: {str(e)}")
            raise AgentError(
                f"Agent initialization failed: {str(e)}",
                details={"agent_type": "benefit_accumulator", "error_type": type(e).__name__}
            )

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
        Parse the Strands agent response to extract benefit accumulator result.

        The agent response contains the tool execution results. We need to
        extract the structured data returned by the get_benefit_accumulator tool.

        Args:
            response: Response from agent.invoke_async()

        Returns:
            Dict[str, Any]: Benefit accumulator lookup result
        """
        import json
        import re

        try:
            import json as json_lib

            # The key insight: Strands agent processes tool calls during invoke_async
            # but the FINAL message in AgentResult.message contains the LLM's response AFTER tool execution
            # We need to look at the state to find tool results OR the message content for the final text

            # Check if response has stop_reason indicating tool use completed
            if hasattr(response, 'stop_reason'):
                logger.info(f"DEBUG: stop_reason = {response.stop_reason}")

            # Try to serialize the entire response to understand its structure
            try:
                response_dict = {
                    'stop_reason': getattr(response, 'stop_reason', None),
                    'message': getattr(response, 'message', None),
                    'state': getattr(response, 'state', None)
                }
                logger.info(f"DEBUG: Full response structure = {json_lib.dumps(response_dict, default=str, indent=2)[:1000]}")
            except Exception as e:
                logger.info(f"DEBUG: Could not serialize response: {e}")

            # Handle object responses with tool_calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"DEBUG: Found {len(response.tool_calls)} tool_calls")
                for i, tool_call in enumerate(response.tool_calls):
                    logger.info(f"DEBUG: Tool call {i} - has result: {hasattr(tool_call, 'result')}")
                    if hasattr(tool_call, 'result'):
                        logger.info(f"DEBUG: Tool result type: {type(tool_call.result)}")
                        logger.info(f"DEBUG: Tool result (first 500 chars): {str(tool_call.result)[:500]}")
                        if isinstance(tool_call.result, dict):
                            return tool_call.result
                        # Try to parse if it's a string
                        try:
                            return json.loads(str(tool_call.result))
                        except:
                            pass

            # Handle object responses with content
            if hasattr(response, 'content'):
                logger.info(f"DEBUG: Found content type: {type(response.content)}")
                response_str = response.content
            else:
                response_str = str(response)

            # Convert to string if needed
            if not isinstance(response_str, str):
                response_str = str(response_str)

            logger.info(f"DEBUG: Attempting to parse string (first 300 chars): {response_str[:300]}")

            try:
                # Direct JSON
                return json.loads(response_str)
            except json.JSONDecodeError:
                # Extract JSON substring if wrapped inside text
                match = re.search(r"\{.*\}", response_str, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass

            # If all fails
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
            ValidationError: If member_id not provided
            AgentError: If agent execution fails

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
            raise ValidationError(
                "member_id is required",
                details={"operation": "benefit_accumulator_lookup"}
            )

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
        except (ConfigError, AgentError) as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {"error": f"Lookup service unavailable: {str(e)}"}

        # Execute lookup via agent
        try:
            logger.info("=" * 60)
            logger.info("EXECUTING BENEFIT ACCUMULATOR LOOKUP")
            logger.info("=" * 60)
            logger.debug(f"Invoking benefit accumulator lookup with params: {params}")

            # WORKAROUND: Due to Strands AgentResult not capturing tool results properly,
            # we directly call the tool function instead of going through the LLM.
            # The tool provides the same structured output that the LLM would have returned.
            from .tools import get_benefit_accumulator as tool_func

            logger.info(f"Calling get_benefit_accumulator tool directly with params: {params}")
            result = await tool_func(params)

            logger.info(
                f"Lookup completed",
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
