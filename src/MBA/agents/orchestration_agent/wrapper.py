"""
High-level wrapper for Orchestration Agent.

This module provides a production-grade interface for the Strands-based
orchestration agent, enabling intelligent multi-agent routing and coordination
in the MBA system.

The wrapper encapsulates:
- AWS Bedrock LLM integration via Strands
- Query analysis and intent classification
- Intelligent agent routing and execution
- Conversation context management
- Comprehensive error handling

Usage:
    agent = OrchestrationAgent()
    result = await agent.process_query("Is member M1001 active?")
"""

from typing import Dict, Any, Optional, List

from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError, AgentError, ValidationError

logger = get_logger(__name__)


class OrchestrationAgent:
    """
    Production wrapper for AWS Bedrock-powered orchestration agent.

    Provides a clean async interface to the Strands agent orchestration
    layer, handling initialization, query processing, agent routing, and
    response normalization for multi-agent workflows.

    This class integrates:
    - AWS Bedrock language models via boto3
    - Strands agent orchestration framework
    - 6 specialized MBA agents
    - Intent classification and entity extraction
    - Structured logging and error handling

    Attributes:
        _agent: Underlying Strands Agent instance
        _initialized: Initialization state flag
        _conversation_history: Optional conversation context

    Thread Safety:
        Not thread-safe. Create separate instances per thread/task.
    """

    def __init__(self):
        """
        Initialize Orchestration Agent wrapper.

        Lazy-loads the Strands agent instance to defer Bedrock client
        initialization until first use. This pattern supports efficient
        Lambda cold starts and testing scenarios.

        Side Effects:
            - Logs wrapper initialization
            - Defers agent initialization to first invocation
        """
        self._agent = None
        self._initialized = False
        self._conversation_history: List[Dict[str, Any]] = []

        logger.info("OrchestrationAgent wrapper created")

    def _ensure_initialized(self):
        """
        Lazy initialization of underlying Strands agent.

        Loads the orchestration agent on first use, enabling fast cold starts
        and reducing initialization overhead in testing environments.

        Raises:
            ConfigError: If agent cannot be initialized
            AgentError: If agent module import fails

        Side Effects:
            - Imports agent module
            - Initializes Bedrock client
            - Registers orchestration tools
            - Sets _initialized flag
        """
        if self._initialized:
            return

        try:
            from .agent import orchestration_agent
            self._agent = orchestration_agent
            self._initialized = True

            logger.info("Orchestration Agent initialized on first use")

        except ImportError as e:
            logger.error(f"Failed to import orchestration agent: {e}")
            raise AgentError(
                f"Agent initialization failed: Cannot import agent module - {str(e)}",
                details={"agent_type": "orchestration", "error_type": "ImportError"}
            )

        except ConfigError as e:
            logger.error(f"Agent configuration error: {e.message}", extra=e.details)
            raise

        except Exception as e:
            logger.error(f"Unexpected error initializing agent: {str(e)}")
            raise AgentError(
                f"Agent initialization failed: {str(e)}",
                details={"agent_type": "orchestration", "error_type": type(e).__name__}
            )

    def _build_orchestration_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Build a natural language prompt for the Bedrock LLM.

        Args:
            query: User's query text
            context: Optional context dictionary

        Returns:
            str: Formatted prompt for the agent
        """
        prompt_parts = [f"User query: {query}"]

        if context:
            prompt_parts.append(f"Context: {context}")

        prompt_parts.append(
            "\nAnalyze this query, identify the appropriate agent, "
            "route to that agent, and provide a helpful response."
        )

        return "\n".join(prompt_parts)

    def _parse_cached_results(self, cached_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse tool results from cache.

        WORKAROUND: Due to Strands AgentResult not capturing tool results properly,
        we retrieve results directly from the global cache that tools populate.

        Args:
            cached_results: Dictionary with tool results from cache

        Returns:
            Dict[str, Any]: Orchestration result
        """
        try:
            analysis_result = cached_results.get('analyze_query')
            routing_result = cached_results.get('route_to_agent')
            format_result = cached_results.get('format_response')

            logger.info(f"Parsing cached results - have analysis: {bool(analysis_result)}, routing: {bool(routing_result)}, format: {bool(format_result)}")

            # Build orchestration result from cached tool results
            if routing_result:
                logger.info("Building result from cached routing_result")
                result = {
                    "success": routing_result.get("success", False),
                    "intent": routing_result.get("intent", "unknown"),
                    "agent": routing_result.get("agent", "Unknown"),
                    "result": routing_result.get("result", {}),
                }

                if analysis_result:
                    result.update({
                        "confidence": analysis_result.get("confidence", 0.0),
                        "reasoning": analysis_result.get("reasoning", ""),
                        "extracted_entities": analysis_result.get("extracted_entities", {})
                    })

                if format_result and format_result.get("success"):
                    result["formatted_response"] = format_result.get("formatted_response", {})

                # Add error if present
                if "error" in routing_result:
                    result["error"] = routing_result["error"]

                return result

            # If no routing result, check if we have analysis result
            if analysis_result:
                logger.warning("Have analysis result but no routing result")
                return {
                    "success": False,
                    "error": "Query analysis succeeded but routing failed",
                    "intent": analysis_result.get("intent", "unknown"),
                    "confidence": analysis_result.get("confidence", 0.0),
                    "reasoning": analysis_result.get("reasoning", ""),
                    "extracted_entities": analysis_result.get("extracted_entities", {})
                }

            # Fallback: no cached results found
            logger.warning("No cached tool results found")
            return {"error": "No tool results captured", "success": False}

        except Exception as e:
            logger.error(f"Error parsing cached results: {str(e)}", exc_info=True)
            return {"error": f"Cached results parsing failed: {str(e)}", "success": False}

    def _parse_agent_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse the Strands agent response to extract orchestration result.

        The agent response contains tool execution results. We need to
        extract the final orchestrated response.

        Args:
            response: Response from agent.invoke_async()

        Returns:
            Dict[str, Any]: Orchestration result
        """
        try:
            # Strands agent stores tool execution history in the response
            # Check for execution_history or history attribute
            analysis_result = None
            routing_result = None
            format_result = None

            # Try to access execution history from different possible attributes
            execution_history = None
            if hasattr(response, 'execution_history'):
                execution_history = response.execution_history
            elif hasattr(response, 'history'):
                execution_history = response.history
            elif hasattr(response, 'tool_calls'):
                execution_history = response.tool_calls
            elif hasattr(response, '_history'):
                execution_history = response._history

            # If we have execution history, extract tool results
            if execution_history:
                logger.info(f"Found execution history with {len(execution_history)} entries")

                for entry in execution_history:
                    # Handle different entry structures
                    tool_name = None
                    tool_result = None

                    if isinstance(entry, dict):
                        tool_name = entry.get('name') or entry.get('tool_name')
                        tool_result = entry.get('result') or entry.get('output')
                    elif hasattr(entry, 'name'):
                        tool_name = entry.name
                        tool_result = getattr(entry, 'result', None) or getattr(entry, 'output', None)

                    if tool_name and tool_result:
                        logger.info(f"Processing tool result from: {tool_name}")
                        if tool_name == 'analyze_query':
                            analysis_result = tool_result if isinstance(tool_result, dict) else {}
                        elif tool_name == 'route_to_agent':
                            routing_result = tool_result if isinstance(tool_result, dict) else {}
                        elif tool_name == 'format_response':
                            format_result = tool_result if isinstance(tool_result, dict) else {}

            # Build orchestration result from tool results
            if routing_result:
                logger.info("Building result from routing_result")
                result = {
                    "success": routing_result.get("success", False),
                    "intent": routing_result.get("intent", "unknown"),
                    "agent": routing_result.get("agent", "Unknown"),
                    "result": routing_result.get("result", {}),
                }

                if analysis_result:
                    result.update({
                        "confidence": analysis_result.get("confidence", 0.0),
                        "reasoning": analysis_result.get("reasoning", ""),
                        "extracted_entities": analysis_result.get("extracted_entities", {})
                    })

                if format_result and format_result.get("success"):
                    result["formatted_response"] = format_result.get("formatted_response", {})

                # Add error if present
                if "error" in routing_result:
                    result["error"] = routing_result["error"]

                return result

            # If no tool results found, check for content in the response
            if hasattr(response, 'content'):
                import json
                content_str = str(response.content)

                # Try to parse as JSON
                try:
                    parsed = json.loads(content_str)
                    if isinstance(parsed, dict) and 'success' in parsed:
                        logger.info("Successfully parsed response content as JSON")
                        return parsed
                except (json.JSONDecodeError, TypeError):
                    pass

                # Text response - treat as successful with message
                logger.info(f"Agent returned text response: {content_str[:200]}...")
                return {
                    "success": True,
                    "intent": "general_inquiry",
                    "agent": "OrchestrationAgent",
                    "result": {
                        "message": content_str
                    },
                    "confidence": 0.8,
                    "reasoning": "Agent provided text response",
                    "extracted_entities": {}
                }

            # Fallback: return error
            logger.warning("Could not parse agent response - no content or tool results found")
            logger.warning(f"Response type: {type(response)}, attributes: {dir(response)}")
            return {"error": "Failed to parse agent response", "success": False}

        except Exception as e:
            logger.error(f"Error parsing agent response: {str(e)}", exc_info=True)
            return {"error": f"Response parsing failed: {str(e)}", "success": False}

    async def process_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        preserve_history: bool = False
    ) -> Dict[str, Any]:
        """
        Process a user query through intelligent orchestration.

        Orchestrates the complete workflow:
        1. Query analysis and intent classification
        2. Entity extraction (member IDs, service types)
        3. Agent routing based on intent
        4. Agent execution
        5. Response formatting

        Args:
            query: User's query text (required)
            context: Optional context dictionary with additional information
            preserve_history: Whether to maintain conversation history (default: False)

        Returns:
            Dictionary containing orchestration results:
            - success: bool (whether query was processed successfully)
            - intent: str (classified intent)
            - confidence: float (intent classification confidence)
            - agent: str (agent that processed the query)
            - result: Dict (agent execution result)
            - query: str (original query)
            - reasoning: str (intent classification reasoning)
            - extracted_entities: Dict (entities from query)
            - error: str (error message if applicable)

        Raises:
            ValidationError: If query is empty or invalid
            AgentError: If orchestration fails

        Example:
            >>> agent = OrchestrationAgent()
            >>> result = await agent.process_query("Is member M1001 active?")
            >>> print(result)
            {
                "success": True,
                "intent": "member_verification",
                "confidence": 0.95,
                "agent": "MemberVerificationAgent",
                "result": {"valid": True, "member_id": "M1001", ...},
                "query": "Is member M1001 active?",
                ...
            }

        Side Effects:
            - Calls AWS Bedrock API
            - Executes SQL queries (for database agents)
            - Queries vector databases (for RAG agents)
            - Updates conversation history (if preserve_history=True)
            - Logs orchestration workflow
        """
        # Validate query
        if not query or not query.strip():
            logger.error("Orchestration attempted without query")
            raise ValidationError(
                "query is required and cannot be empty",
                details={"operation": "orchestration"}
            )

        query = query.strip()

        logger.info(
            f"Processing query through orchestration",
            extra={"query": query[:100], "has_context": bool(context)}
        )

        # Ensure agent initialized
        try:
            self._ensure_initialized()
        except (ConfigError, AgentError) as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {
                "success": False,
                "error": f"Orchestration service unavailable: {str(e)}",
                "query": query
            }

        try:
            logger.info("=" * 70)
            logger.info("AI-POWERED ORCHESTRATION WORKFLOW STARTED")
            logger.info("=" * 70)

            # Build prompt for the LLM
            prompt = self._build_orchestration_prompt(query, context)

            logger.info(f"Invoking Strands agent with query: {query[:100]}...")

            # Invoke the Strands agent
            # The agent will use its tools (analyze_query, route_to_agent, format_response)
            # to intelligently process the query
            response = await self._agent.invoke_async(prompt)

            logger.info("Strands agent invocation completed")

            # WORKAROUND: Due to Strands AgentResult not capturing tool results properly,
            # we retrieve results from our cache instead of parsing the response object
            from .tools import get_tool_results_cache, clear_tool_results_cache

            # Get cached tool results
            cached_results = get_tool_results_cache()
            logger.info(f"Retrieved cached tool results: {list(cached_results.keys())}")

            # Parse the results from cache
            result = self._parse_cached_results(cached_results)

            # Clear cache for next invocation
            clear_tool_results_cache()

            # Ensure query is in result
            if "query" not in result:
                result["query"] = query

            # Preserve conversation history if requested
            if preserve_history and result.get("success"):
                self._conversation_history.append({
                    "query": query,
                    "intent": result.get("intent"),
                    "confidence": result.get("confidence"),
                    "agent": result.get("agent"),
                    "success": result.get("success"),
                    "timestamp": None
                })

            logger.info(
                f"Orchestration completed",
                extra={
                    "success": result.get("success", False),
                    "intent": result.get("intent"),
                    "agent": result.get("agent")
                }
            )
            logger.info("=" * 70)

            return result

        except Exception as e:
            logger.error(
                f"Orchestration failed: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__, "query": query}
            )

            return {
                "success": False,
                "error": f"Orchestration failed: {str(e)}",
                "query": query,
                "intent": "unknown",
                "confidence": 0.0
            }

    async def process_batch(
        self,
        queries: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process multiple queries in batch through orchestration.

        Useful for processing conversation history or multiple user questions
        simultaneously.

        Args:
            queries: List of query strings to process
            context: Optional shared context for all queries

        Returns:
            List of orchestration results, one per query

        Example:
            >>> agent = OrchestrationAgent()
            >>> queries = [
            ...     "Is member M1001 active?",
            ...     "What is the deductible for member M1234?",
            ... ]
            >>> results = await agent.process_batch(queries)

        Side Effects:
            - Processes all queries through orchestration
            - Logs batch processing progress
        """
        if not queries:
            logger.warning("Batch processing called with empty query list")
            return []

        logger.info(f"Batch orchestration requested for {len(queries)} queries")

        results = []
        for idx, query in enumerate(queries, 1):
            logger.info(f"Processing query {idx}/{len(queries)}")
            result = await self.process_query(query, context, preserve_history=False)
            results.append(result)

        logger.info(
            f"Batch orchestration completed: {len(results)} results",
            extra={
                "successful": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success"))
            }
        )

        return results

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history for this orchestration instance.

        Returns:
            List of conversation entries (only if preserve_history=True was used)

        Example:
            >>> agent = OrchestrationAgent()
            >>> await agent.process_query("Is member M1001 active?", preserve_history=True)
            >>> history = agent.get_conversation_history()
            >>> print(len(history))
            1
        """
        return self._conversation_history.copy()

    def clear_conversation_history(self):
        """
        Clear the conversation history.

        Side Effects:
            - Clears internal conversation history list
        """
        self._conversation_history.clear()
        logger.info("Conversation history cleared")

    def get_available_agents(self) -> List[str]:
        """
        Get list of available specialized agents.

        Returns:
            List of agent names

        Example:
            >>> agent = OrchestrationAgent()
            >>> agents = agent.get_available_agents()
            >>> print(agents)
            ['IntentIdentificationAgent', 'MemberVerificationAgent', ...]
        """
        return [
            "IntentIdentificationAgent",
            "MemberVerificationAgent",
            "DeductibleOOPAgent",
            "BenefitAccumulatorAgent",
            "BenefitCoverageRAGAgent",
            "LocalRAGAgent"
        ]
