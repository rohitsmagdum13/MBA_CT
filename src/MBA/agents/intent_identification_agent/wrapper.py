"""
High-level wrapper for Intent Identification Agent.

Provides a production-grade interface for intent classification and query routing
in the MBA system.
"""

from typing import Dict, Any, Optional

from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError

logger = get_logger(__name__)


class IntentIdentificationAgent:
    """
    Production wrapper for intent identification and query routing.

    This class provides a clean async interface to the Strands-based intent
    classification agent, enabling intelligent routing of user queries to
    the appropriate MBA system agent.

    Attributes:
        _initialized: Initialization state flag

    Thread Safety:
        Not thread-safe. Create separate instances per thread/task.
    """

    def __init__(self):
        """
        Initialize Intent Identification Agent wrapper.

        Lazy-loads the Strands agent to defer initialization until first use.

        Side Effects:
            - Logs wrapper initialization
            - Defers agent initialization to first invocation
        """
        self._initialized = False
        logger.info("IntentIdentificationAgent wrapper created")

    def _ensure_initialized(self):
        """
        Lazy initialization of underlying Strands agent.

        Loads the intent agent on first use, enabling fast cold starts.

        Raises:
            ConfigError: If agent cannot be initialized
            RuntimeError: If agent module import fails

        Side Effects:
            - Imports agent module
            - Initializes Bedrock client
            - Registers intent classification tools
            - Sets _initialized flag
        """
        if self._initialized:
            return

        try:
            # Import agent to trigger initialization
            from . import agent
            self._initialized = True
            logger.info("Intent Identification Agent initialized on first use")

        except ImportError as e:
            logger.error(f"Failed to import intent identification agent: {e}")
            raise RuntimeError(
                f"Agent initialization failed: Cannot import agent module - {str(e)}"
            )

        except ConfigError as e:
            logger.error(f"Agent configuration error: {e.message}", extra=e.details)
            raise

        except Exception as e:
            logger.error(f"Unexpected error initializing agent: {str(e)}")
            raise RuntimeError(f"Agent initialization failed: {str(e)}")

    async def identify(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Identify intent from user query.

        Analyzes the user's query and classifies it into one of the supported
        intent categories for routing to the appropriate agent.

        Args:
            query: User's query text (required)
            context: Optional context dictionary with additional information

        Returns:
            Dictionary containing classification results:
                - success: bool
                - intent: str (intent code)
                - confidence: float (0.0-1.0)
                - reasoning: str (classification explanation)
                - extracted_entities: Dict (extracted entities from query)
                - suggested_agent: str (agent name to handle request)
                - fallback_intent: str (alternative intent if primary fails)
                - pattern_matches: Dict (pattern matching scores for debugging)
                - query: str (original query)

        Raises:
            ValueError: If query is empty or invalid
            RuntimeError: If agent execution fails

        Example:
            >>> agent = IntentIdentificationAgent()
            >>> result = await agent.identify("Is member M1001 active?")
            >>> print(result)
            {
                "success": True,
                "intent": "member_verification",
                "confidence": 0.95,
                "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
                "extracted_entities": {
                    "member_id": "M1001",
                    "query_type": "status"
                },
                "suggested_agent": "MemberVerificationAgent",
                "fallback_intent": "general_inquiry",
                "pattern_matches": {...},
                "query": "Is member M1001 active?"
            }

        Side Effects:
            - Calls AWS Bedrock API (if LLM classification is used)
            - Logs classification attempts and results
        """
        # Validate query
        if not query or not query.strip():
            logger.error("Intent identification attempted without query")
            raise ValueError("query is required and cannot be empty")

        # Build parameters
        params = {"query": query.strip()}
        if context:
            params["context"] = context

        logger.info(
            f"Intent identification requested",
            extra={"query": query[:100], "has_context": bool(context)}
        )

        # Ensure agent initialized
        try:
            self._ensure_initialized()
        except (ConfigError, RuntimeError) as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {
                "success": False,
                "error": f"Intent service unavailable: {str(e)}",
                "intent": "general_inquiry",
                "confidence": 0.0
            }

        # Execute intent identification via direct tool call
        try:
            logger.info("=" * 60)
            logger.info("EXECUTING INTENT IDENTIFICATION")
            logger.info("=" * 60)

            # WORKAROUND: Call tool directly (same pattern as other agents)
            from .tools import identify_intent

            logger.info(f"Calling identify_intent tool with query: {query[:100]}...")
            result = await identify_intent(params)

            logger.info(
                f"Intent identification completed",
                extra={
                    "success": result.get("success", False),
                    "intent": result.get("intent"),
                    "confidence": result.get("confidence", 0.0)
                }
            )
            logger.info("=" * 60)

            return result

        except Exception as e:
            logger.error(
                f"Intent identification failed: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )

            return {
                "success": False,
                "error": f"Intent identification failed: {str(e)}",
                "intent": "general_inquiry",
                "confidence": 0.0,
                "query": query
            }

    async def classify_batch(
        self,
        queries: list[str],
        context: Optional[Dict[str, Any]] = None
    ) -> list[Dict[str, Any]]:
        """
        Classify multiple queries in batch.

        Useful for processing multiple user queries or analyzing conversation history.

        Args:
            queries: List of query strings to classify
            context: Optional shared context for all queries

        Returns:
            List of classification results, one per query

        Example:
            >>> agent = IntentIdentificationAgent()
            >>> queries = [
            ...     "Is member M1001 active?",
            ...     "What is the deductible?",
            ...     "How many massage visits used?"
            ... ]
            >>> results = await agent.classify_batch(queries)
            >>> for result in results:
            ...     print(f"{result['intent']}: {result['confidence']}")

        Side Effects:
            - Makes multiple API calls (one per query)
            - Logs batch processing progress
        """
        if not queries:
            logger.warning("Batch classification called with empty query list")
            return []

        logger.info(f"Batch classification requested for {len(queries)} queries")

        results = []
        for idx, query in enumerate(queries, 1):
            logger.info(f"Processing query {idx}/{len(queries)}")
            result = await self.identify(query, context)
            results.append(result)

        logger.info(f"Batch classification completed: {len(results)} results")
        return results

    def get_supported_intents(self) -> list[str]:
        """
        Get list of supported intent codes.

        Returns:
            List of valid intent codes

        Example:
            >>> agent = IntentIdentificationAgent()
            >>> intents = agent.get_supported_intents()
            >>> print(intents)
            ['member_verification', 'deductible_oop', 'benefit_accumulator',
             'benefit_coverage_rag', 'local_rag', 'general_inquiry']
        """
        from .tools import VALID_INTENTS
        return VALID_INTENTS.copy()

    def get_agent_mapping(self) -> Dict[str, str]:
        """
        Get mapping of intents to agent names.

        Returns:
            Dictionary mapping intent codes to agent class names

        Example:
            >>> agent = IntentIdentificationAgent()
            >>> mapping = agent.get_agent_mapping()
            >>> print(mapping['member_verification'])
            'MemberVerificationAgent'
        """
        return {
            "member_verification": "MemberVerificationAgent",
            "deductible_oop": "DeductibleOOPAgent",
            "benefit_accumulator": "BenefitAccumulatorAgent",
            "benefit_coverage_rag": "BenefitCoverageRAGAgent",
            "local_rag": "LocalRAGAgent",
            "general_inquiry": "None"
        }
