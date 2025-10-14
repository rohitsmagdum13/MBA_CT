"""
Tools for Intent Identification Agent.

Provides functions for analyzing user queries and classifying intents
for routing to appropriate MBA system agents.
"""

import json
import re
from typing import Dict, Any, List
from strands import tool

from ...core.logging_config import get_logger

logger = get_logger(__name__)

# Intent codes
VALID_INTENTS = [
    "member_verification",
    "deductible_oop",
    "benefit_accumulator",
    "benefit_coverage_rag",
    "local_rag",
    "general_inquiry"
]

# Keyword patterns for intent detection
INTENT_PATTERNS = {
    "member_verification": [
        r'\bmember\s+(?:id\s+)?[mM]\d+',
        r'\bverify\s+member',
        r'\bmember\s+status',
        r'\bmember\s+eligibility',
        r'\bis\s+member\s+\w+\s+(?:active|enrolled|valid)',
        r'\bcheck\s+eligibility'
    ],
    "deductible_oop": [
        r'\bdeductible',
        r'\bout[-\s]of[-\s]pocket',
        r'\boop\b',
        r'\bmaximum\s+(?:out[-\s]of[-\s]pocket|oop)',
        r'\bremaining\s+deductible',
        r'\bmet\s+(?:the\s+)?deductible'
    ],
    "benefit_accumulator": [
        r'\bhow\s+many\s+(?:visits|sessions)',
        r'\bvisit\s+count',
        r'\bvisit\s+limit',
        r'\bused\s+\d+\s+(?:visits|sessions)',
        r'\bremaining\s+(?:visits|sessions)',
        r'\baccumulator',
        r'\bmassage\s+(?:therapy\s+)?(?:visits|limit)',
        r'\bchiropractic\s+(?:visits|limit)',
        r'\bacupuncture\s+(?:visits|limit)',
        r'\blimit\s+reached'
    ],
    "benefit_coverage_rag": [
        r'\bis\s+\w+\s+covered',
        r'\bcoverage\s+for',
        r'\bwhat\s+(?:is|are)\s+(?:the\s+)?(?:copays?|coinsurance)',
        r'\bplan\s+(?:details|coverage|benefits)',
        r'\bpolicy\s+(?:details|coverage)',
        r'\bwhat\s+services\s+(?:are\s+)?covered',
        r'\bpreventive\s+(?:care|services)',
        r'\bcovered\s+at\s+\d+%'
    ],
    "local_rag": [
        r'\buploaded\s+document',
        r'\bbenefit\s+(?:document|pdf)',
        r'\bsearch\s+(?:the\s+)?document',
        r'\bquery\s+(?:the\s+)?(?:uploaded|document)',
        r'\bin\s+the\s+pdf',
        r'\bwhat\s+does\s+(?:the\s+)?document\s+say'
    ],
    "general_inquiry": [
        r'^(?:hello|hi|hey|greetings)',
        r'\bhelp\b',
        r'\bwhat\s+can\s+(?:you|this)',
        r'\bhow\s+(?:do\s+i|to)\s+use',
        r'\btell\s+me\s+about'
    ]
}


def extract_member_id(query: str) -> str | None:
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


def extract_service_type(query: str) -> str | None:
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
        "surgery", "surgical"
    ]

    query_lower = query.lower()
    for service in services:
        if service in query_lower:
            return service

    return None


def calculate_confidence(query: str, intent: str) -> float:
    """
    Calculate confidence score for intent classification.

    Args:
        query: User query
        intent: Classified intent

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if intent not in INTENT_PATTERNS:
        return 0.5

    patterns = INTENT_PATTERNS[intent]
    matches = 0

    for pattern in patterns:
        if re.search(pattern, query, re.IGNORECASE):
            matches += 1

    if matches == 0:
        return 0.3
    elif matches == 1:
        return 0.6
    elif matches == 2:
        return 0.8
    else:
        return 0.95


def detect_intent_patterns(query: str) -> Dict[str, int]:
    """
    Detect patterns for each intent in the query.

    Args:
        query: User query

    Returns:
        Dictionary mapping intent to match count
    """
    intent_matches = {}

    for intent, patterns in INTENT_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                matches += 1
        intent_matches[intent] = matches

    return intent_matches


@tool
async def identify_intent(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Identify user intent from query for routing to appropriate agent.

    This is the main tool that the Strands agent will call. It performs
    pattern-based pre-classification to help guide the LLM's decision.

    Args:
        params: Dictionary containing:
            - query (str): User's query text
            - context (dict, optional): Additional context

    Returns:
        Dictionary with intent classification results:
            - intent: Identified intent code
            - confidence: Confidence score (0.0-1.0)
            - reasoning: Explanation of classification
            - extracted_entities: Extracted entities from query
            - suggested_agent: Agent name to handle request
            - fallback_intent: Alternative intent if primary fails
            - pattern_matches: Pattern matching scores for debugging
    """
    try:
        query = params.get("query", "").strip()
        context = params.get("context", {})

        if not query:
            return {
                "success": False,
                "error": "Query is required"
            }

        logger.info(f"Identifying intent for query: {query[:100]}...")

        # Pattern-based pre-classification
        pattern_matches = detect_intent_patterns(query)

        # Find intent with most pattern matches
        if max(pattern_matches.values()) > 0:
            primary_intent = max(pattern_matches, key=pattern_matches.get)
            confidence = calculate_confidence(query, primary_intent)
        else:
            # Default to general inquiry if no patterns match
            primary_intent = "general_inquiry"
            confidence = 0.7

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
        if "status" in query_lower or "active" in query_lower:
            extracted_entities["query_type"] = "status"
        elif "coverage" in query_lower or "covered" in query_lower:
            extracted_entities["query_type"] = "coverage"
        elif any(word in query_lower for word in ["how many", "count", "used", "remaining"]):
            extracted_entities["query_type"] = "usage_count"
        elif any(word in query_lower for word in ["deductible", "oop", "out-of-pocket", "paid"]):
            extracted_entities["query_type"] = "financial"

        # Map intent to agent
        agent_mapping = {
            "member_verification": "MemberVerificationAgent",
            "deductible_oop": "DeductibleOOPAgent",
            "benefit_accumulator": "BenefitAccumulatorAgent",
            "benefit_coverage_rag": "BenefitCoverageRAGAgent",
            "local_rag": "LocalRAGAgent",
            "general_inquiry": "None"
        }

        suggested_agent = agent_mapping.get(primary_intent, "None")

        # Determine fallback intent
        fallback_map = {
            "member_verification": "general_inquiry",
            "deductible_oop": "benefit_accumulator",
            "benefit_accumulator": "deductible_oop",
            "benefit_coverage_rag": "local_rag",
            "local_rag": "benefit_coverage_rag",
            "general_inquiry": "benefit_coverage_rag"
        }

        fallback_intent = fallback_map.get(primary_intent, "general_inquiry")

        # Generate reasoning
        reasoning_parts = []
        if member_id:
            reasoning_parts.append(f"Detected member ID: {member_id}")
        if service_type:
            reasoning_parts.append(f"Detected service type: {service_type}")
        reasoning_parts.append(f"Pattern matches: {pattern_matches[primary_intent]} for {primary_intent}")

        reasoning = ". ".join(reasoning_parts) if reasoning_parts else "Based on query analysis"

        result = {
            "success": True,
            "intent": primary_intent,
            "confidence": round(confidence, 2),
            "reasoning": reasoning,
            "extracted_entities": extracted_entities,
            "suggested_agent": suggested_agent,
            "fallback_intent": fallback_intent,
            "pattern_matches": pattern_matches,
            "query": query
        }

        logger.info(
            f"Intent identified: {primary_intent} (confidence: {confidence:.2f})",
            extra={"intent": primary_intent, "confidence": confidence, "entities": extracted_entities}
        )

        return result

    except Exception as e:
        logger.error(f"Intent identification failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Intent identification failed: {str(e)}",
            "intent": "general_inquiry",
            "confidence": 0.0
        }


@tool
async def validate_intent_response(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and parse LLM's intent classification response.

    Args:
        params: Dictionary containing:
            - response (str): LLM's JSON response

    Returns:
        Validated and parsed intent classification
    """
    try:
        response = params.get("response", "")

        # Try to parse JSON
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                return {
                    "success": False,
                    "error": "Invalid JSON response"
                }

        # Validate required fields
        required_fields = ["intent", "confidence", "reasoning"]
        for field in required_fields:
            if field not in parsed:
                return {
                    "success": False,
                    "error": f"Missing required field: {field}"
                }

        # Validate intent
        if parsed["intent"] not in VALID_INTENTS:
            return {
                "success": False,
                "error": f"Invalid intent: {parsed['intent']}"
            }

        # Validate confidence
        confidence = parsed["confidence"]
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            return {
                "success": False,
                "error": f"Invalid confidence value: {confidence}"
            }

        return {
            "success": True,
            **parsed
        }

    except Exception as e:
        logger.error(f"Response validation failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Validation failed: {str(e)}"
        }
