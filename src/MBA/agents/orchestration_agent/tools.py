"""
Tools for Orchestration Agent.

Provides functions for query analysis and agent routing in the MBA system.
"""

import json
import re
from typing import Dict, Any, Optional
from strands import tool

from ...core.logging_config import get_logger

logger = get_logger(__name__)


def extract_member_id(query: str) -> Optional[str]:
    """
    Extract member ID from query.

    Args:
        query: User query string

    Returns:
        Member ID if found, None otherwise
    """
    # Pattern: M followed by digits (e.g., M1001, M1234)
    pattern = r'\b[mM](\d{3,})\b'
    match = re.search(pattern, query)
    if match:
        return f"M{match.group(1)}"
    return None


def extract_service_type(query: str) -> Optional[str]:
    """
    Extract service/benefit type from query.

    Args:
        query: User query string

    Returns:
        Service type if found, None otherwise
    """
    # Common service types
    services = [
        "massage therapy", "massage",
        "chiropractic", "chiropractor",
        "acupuncture",
        "physical therapy", "PT",
        "mental health", "therapy",
        "preventive care", "preventive",
        "emergency room", "ER",
        "urgent care",
        "hospitalization", "inpatient",
        "surgery", "surgical",
        "dental", "dentist",
        "vision", "optical"
    ]

    query_lower = query.lower()
    for service in services:
        if service in query_lower:
            return service

    return None


def classify_intent(query: str) -> tuple[str, float]:
    """
    Classify the intent of a query using pattern matching.

    Args:
        query: User query string

    Returns:
        Tuple of (intent_code, confidence_score)
    """
    query_lower = query.lower()

    # Intent patterns with priority
    patterns = {
        "member_verification": [
            (r'\bmember\s+(?:id\s+)?[mM]\d+', 0.3),
            (r'\bverify\s+member', 0.2),
            (r'\bmember\s+status', 0.2),
            (r'\bis\s+member\s+\w+\s+(?:active|enrolled|valid)', 0.2),
            (r'\bcheck\s+eligibility', 0.1)
        ],
        "deductible_oop": [
            (r'\bdeductible', 0.4),
            (r'\bout[-\s]of[-\s]pocket', 0.3),
            (r'\boop\b', 0.2),
            (r'\bmaximum\s+(?:out[-\s]of[-\s]pocket|oop)', 0.1)
        ],
        "benefit_accumulator": [
            (r'\bhow\s+many\s+(?:visits|sessions)', 0.3),
            (r'\bvisit\s+(?:count|limit)', 0.2),
            (r'\bremaining\s+(?:visits|sessions)', 0.2),
            (r'\baccumulator', 0.2),
            (r'\blimit\s+reached', 0.1)
        ],
        "benefit_coverage_rag": [
            (r'\bis\s+\w+\s+covered', 0.3),
            (r'\bcoverage\s+for', 0.2),
            (r'\bwhat\s+(?:is|are)\s+(?:the\s+)?(?:copays?|coinsurance)', 0.2),
            (r'\bplan\s+(?:details|coverage|benefits)', 0.2),
            (r'\bwhat\s+services\s+(?:are\s+)?covered', 0.1)
        ],
        "local_rag": [
            (r'\buploaded\s+document', 0.4),
            (r'\bbenefit\s+(?:document|pdf)', 0.3),
            (r'\bsearch\s+(?:the\s+)?document', 0.2),
            (r'\bin\s+the\s+pdf', 0.1)
        ],
        "general_inquiry": [
            (r'^(?:hello|hi|hey|greetings)', 0.4),
            (r'\bhelp\b', 0.3),
            (r'\bwhat\s+can\s+(?:you|this)', 0.2),
            (r'\btell\s+me\s+about', 0.1)
        ]
    }

    # Calculate scores for each intent
    scores = {}
    for intent, intent_patterns in patterns.items():
        score = 0.0
        for pattern, weight in intent_patterns:
            if re.search(pattern, query_lower):
                score += weight
        scores[intent] = score

    # Find intent with highest score
    if max(scores.values()) > 0:
        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent], 1.0)  # Cap at 1.0

        # Special handling for usage/count queries - prioritize benefit_accumulator
        if any(word in query_lower for word in ["how many", "count", "used", "remaining", "visit"]):
            if extract_service_type(query) or "visit" in query_lower:
                best_intent = "benefit_accumulator"
                confidence = min(scores.get("benefit_accumulator", 0) + 0.3, 1.0)

        # Boost confidence if member ID present for member-specific intents
        if best_intent in ["member_verification", "deductible_oop", "benefit_accumulator"]:
            if extract_member_id(query):
                confidence = min(confidence + 0.15, 1.0)

        return best_intent, confidence
    else:
        return "general_inquiry", 0.7


def determine_agent_for_intent(intent: str) -> str:
    """
    Map intent to agent name.

    Args:
        intent: Intent code

    Returns:
        Agent name
    """
    agent_mapping = {
        "member_verification": "MemberVerificationAgent",
        "deductible_oop": "DeductibleOOPAgent",
        "benefit_accumulator": "BenefitAccumulatorAgent",
        "benefit_coverage_rag": "BenefitCoverageRAGAgent",
        "local_rag": "LocalRAGAgent",
        "general_inquiry": "OrchestrationAgent"
    }
    return agent_mapping.get(intent, "OrchestrationAgent")


@tool
async def analyze_query(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze user query to classify intent and extract entities.

    This tool performs the first step of orchestration: understanding
    what the user wants and which agent should handle it.

    Args:
        params: Dictionary containing:
            - query (str): User's query text
            - context (dict, optional): Additional context

    Returns:
        Dictionary with analysis results:
            - intent: Classified intent code
            - confidence: Confidence score (0.0-1.0)
            - agent: Suggested agent name
            - extracted_entities: Dict of extracted entities
            - reasoning: Explanation of classification
            - requires_routing: Boolean indicating if agent routing needed
    """
    try:
        query = params.get("query", "").strip()
        context = params.get("context", {})

        if not query:
            return {
                "success": False,
                "error": "Query is required"
            }

        logger.info(f"Analyzing query for orchestration: {query[:100]}...")

        # Classify intent
        intent, confidence = classify_intent(query)

        # Extract entities
        extracted_entities = {}

        member_id = extract_member_id(query)
        if member_id:
            extracted_entities["member_id"] = member_id

        service_type = extract_service_type(query)
        if service_type:
            extracted_entities["service_type"] = service_type

        # Determine query type
        query_lower = query.lower()
        if "status" in query_lower or "active" in query_lower or "enrolled" in query_lower:
            extracted_entities["query_type"] = "status"
        elif "coverage" in query_lower or "covered" in query_lower:
            extracted_entities["query_type"] = "coverage"
        elif any(word in query_lower for word in ["how many", "count", "used", "remaining"]):
            extracted_entities["query_type"] = "usage_count"
        elif any(word in query_lower for word in ["deductible", "oop", "out-of-pocket", "paid"]):
            extracted_entities["query_type"] = "financial"

        # Determine agent
        agent = determine_agent_for_intent(intent)

        # Build reasoning
        reasoning_parts = []
        if member_id:
            reasoning_parts.append(f"Detected member ID: {member_id}")
        if service_type:
            reasoning_parts.append(f"Detected service type: {service_type}")
        reasoning_parts.append(f"Intent classified as: {intent}")
        reasoning_parts.append(f"Confidence: {confidence:.2f}")

        reasoning = ". ".join(reasoning_parts)

        # Determine if routing is needed
        requires_routing = intent != "general_inquiry"

        result = {
            "success": True,
            "intent": intent,
            "confidence": round(confidence, 2),
            "agent": agent,
            "extracted_entities": extracted_entities,
            "reasoning": reasoning,
            "requires_routing": requires_routing,
            "query": query
        }

        logger.info(
            f"Query analysis complete: {intent} -> {agent} (confidence: {confidence:.2f})",
            extra={"intent": intent, "agent": agent, "entities": extracted_entities}
        )

        return result

    except Exception as e:
        logger.error(f"Query analysis failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Query analysis failed: {str(e)}",
            "intent": "general_inquiry",
            "confidence": 0.0
        }


@tool
async def route_to_agent(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route query to the appropriate specialized agent and execute.

    This tool performs the second step of orchestration: executing
    the selected agent's workflow with the extracted parameters.

    Args:
        params: Dictionary containing:
            - intent (str): Classified intent code
            - agent (str): Target agent name
            - query (str): Original user query
            - extracted_entities (dict): Extracted entities
            - context (dict, optional): Additional context

    Returns:
        Dictionary with agent execution results:
            - success: Boolean indicating success
            - agent: Agent that processed the request
            - result: Agent's response data
            - error: Error message if failed
    """
    try:
        intent = params.get("intent")
        agent_name = params.get("agent")
        query = params.get("query", "")
        extracted_entities = params.get("extracted_entities", {})
        context = params.get("context", {})

        logger.info(f"Routing to agent: {agent_name} for intent: {intent}")

        # Import agents dynamically to avoid circular imports
        from ..member_verification_agent import MemberVerificationAgent
        from ..deductible_oop_agent import DeductibleOOPAgent
        from ..benefit_accumulator_agent import BenefitAccumulatorAgent
        from ..benefit_coverage_rag_agent import BenefitCoverageRAGAgent
        from ..local_rag_agent import LocalRAGAgent

        # Route based on intent
        if intent == "member_verification":
            member_id = extracted_entities.get("member_id")
            dob = extracted_entities.get("dob")
            name = extracted_entities.get("name")

            if not member_id and not dob and not name:
                return {
                    "success": False,
                    "error": "Missing required information. Please provide member ID, date of birth, or name.",
                    "agent": agent_name,
                    "intent": intent
                }

            agent = MemberVerificationAgent()
            result = await agent.verify_member(
                member_id=member_id,
                dob=dob,
                name=name
            )

            return {
                "success": result.get("valid", False) if "valid" in result else not ("error" in result),
                "agent": agent_name,
                "intent": intent,
                "result": result
            }

        elif intent == "deductible_oop":
            member_id = extracted_entities.get("member_id")

            if not member_id:
                return {
                    "success": False,
                    "error": "Member ID is required for deductible/OOP lookup. Please provide a member ID (e.g., M1001).",
                    "agent": agent_name,
                    "intent": intent
                }

            agent = DeductibleOOPAgent()
            result = await agent.get_deductible_oop(member_id=member_id)

            return {
                "success": result.get("found", False),
                "agent": agent_name,
                "intent": intent,
                "result": result
            }

        elif intent == "benefit_accumulator":
            member_id = extracted_entities.get("member_id")
            service_type = extracted_entities.get("service_type")

            if not member_id:
                return {
                    "success": False,
                    "error": "Member ID is required for benefit accumulator lookup. Please provide a member ID (e.g., M1001).",
                    "agent": agent_name,
                    "intent": intent
                }

            agent = BenefitAccumulatorAgent()
            result = await agent.get_benefit_accumulator(
                member_id=member_id,
                service=service_type  # Parameter name is 'service' not 'service_type'
            )

            return {
                "success": result.get("found", False),
                "agent": agent_name,
                "intent": intent,
                "result": result
            }

        elif intent == "benefit_coverage_rag":
            agent = BenefitCoverageRAGAgent()
            result = await agent.query(question=query, k=5)

            return {
                "success": "answer" in result and not result.get("error"),
                "agent": agent_name,
                "intent": intent,
                "result": result
            }

        elif intent == "local_rag":
            agent = LocalRAGAgent()
            result = await agent.query(question=query, k=5)

            return {
                "success": "answer" in result and not result.get("error"),
                "agent": agent_name,
                "intent": intent,
                "result": result
            }

        elif intent == "general_inquiry":
            # Handle general inquiries directly
            return {
                "success": True,
                "agent": "OrchestrationAgent",
                "intent": intent,
                "result": {
                    "message": "I'm the MBA system orchestration agent. I can help you with:\n"
                              "- Member verification and eligibility checks\n"
                              "- Deductible and out-of-pocket information\n"
                              "- Benefit usage and accumulation tracking\n"
                              "- Coverage policy questions\n"
                              "- Queries about uploaded benefit documents\n\n"
                              "What would you like to know?"
                }
            }

        else:
            return {
                "success": False,
                "error": f"Unsupported intent: {intent}",
                "agent": agent_name,
                "intent": intent
            }

    except Exception as e:
        logger.error(f"Agent routing failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Agent routing failed: {str(e)}",
            "agent": params.get("agent", "Unknown"),
            "intent": params.get("intent", "unknown")
        }


@tool
async def format_response(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format agent response for user presentation.

    This tool helps format the raw agent response into a user-friendly
    conversational format.

    Args:
        params: Dictionary containing:
            - agent_result (dict): Result from agent execution
            - intent (str): Intent that was processed
            - query (str): Original query

    Returns:
        Dictionary with formatted response
    """
    try:
        agent_result = params.get("agent_result", {})
        intent = params.get("intent", "")
        query = params.get("query", "")

        # Format based on intent type
        if intent == "member_verification":
            if agent_result.get("valid"):
                member_data = agent_result
                formatted = {
                    "message": f"✅ Member {member_data.get('member_id', 'Unknown')} "
                              f"({member_data.get('name', 'Unknown')}) is **{member_data.get('status', 'active')}** and enrolled.",
                    "details": {
                        "Member ID": member_data.get("member_id"),
                        "Name": member_data.get("name"),
                        "Date of Birth": member_data.get("dob"),
                        "Status": member_data.get("status", "active")
                    }
                }
            else:
                formatted = {
                    "message": f"❌ {agent_result.get('message', 'Member verification failed')}",
                    "details": agent_result
                }

        elif intent == "deductible_oop":
            if agent_result.get("found"):
                formatted = {
                    "message": f"💰 Deductible & Out-of-Pocket Information for Member {agent_result.get('member_id')}",
                    "details": agent_result
                }
            else:
                formatted = {
                    "message": f"❌ {agent_result.get('message', 'Deductible information not found')}",
                    "details": agent_result
                }

        elif intent == "benefit_accumulator":
            if agent_result.get("found"):
                formatted = {
                    "message": f"📊 Benefit Usage Information for Member {agent_result.get('member_id')}",
                    "details": agent_result
                }
            else:
                formatted = {
                    "message": f"❌ {agent_result.get('message', 'Benefit information not found')}",
                    "details": agent_result
                }

        elif intent in ["benefit_coverage_rag", "local_rag"]:
            if "answer" in agent_result:
                formatted = {
                    "message": agent_result.get("answer"),
                    "details": {
                        "sources": agent_result.get("sources", []),
                        "confidence": agent_result.get("confidence")
                    }
                }
            else:
                formatted = {
                    "message": f"❌ {agent_result.get('error', 'Unable to retrieve answer')}",
                    "details": agent_result
                }

        else:
            formatted = {
                "message": agent_result.get("message", "Query processed"),
                "details": agent_result
            }

        return {
            "success": True,
            "formatted_response": formatted
        }

    except Exception as e:
        logger.error(f"Response formatting failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Response formatting failed: {str(e)}"
        }
