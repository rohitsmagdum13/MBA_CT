## Intent Identification Agent

**Version**: 1.0.0
**Status**: Production Ready
**Model**: AWS Bedrock Claude Sonnet 4.5
**Framework**: Strands Agent SDK

---

## Overview

The Intent Identification Agent is an intelligent query routing system that analyzes user queries and classifies them into appropriate intent categories. It acts as the first layer in the MBA system, directing queries to the most suitable specialized agent.

### Key Capabilities

- **Multi-Intent Classification**: Identifies 6 distinct intent categories
- **Entity Extraction**: Extracts member IDs, service types, and query types
- **Confidence Scoring**: Provides confidence levels for routing decisions
- **Pattern Matching**: Uses regex-based pre-classification for speed
- **Fallback Handling**: Suggests alternative intents if primary fails
- **Batch Processing**: Supports classification of multiple queries

---

## Supported Intents

| Intent Code | Purpose | Example Queries |
|-------------|---------|-----------------|
| `member_verification` | Verify member eligibility and status | "Is member M1001 active?", "Check eligibility for John Doe" |
| `deductible_oop` | Query deductible and OOP information | "What is the deductible for member M1001?", "Show OOP for M1234" |
| `benefit_accumulator` | Check service usage and limits | "How many massage visits has M1001 used?", "Check chiropractic limit" |
| `benefit_coverage_rag` | Answer policy coverage questions | "Is acupuncture covered?", "What are ER copays?" |
| `local_rag` | Query uploaded documents | "What does the document say about massage?", "Search PDF for benefits" |
| `general_inquiry` | Handle greetings and help requests | "Hello", "What can you help with?", "How do I use this?" |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ User Query                                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ IntentIdentificationAgent                                   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Pattern-Based Pre-Classification                  │  │
│  │    - Regex matching against query                    │  │
│  │    - Fast entity extraction (member ID, services)    │  │
│  │    - Initial confidence scoring                      │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                       │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2. Intent Classification Tool                        │  │
│  │    - Analyzes query against intent patterns          │  │
│  │    - Extracts entities (member_id, service_type)     │  │
│  │    - Calculates confidence score                     │  │
│  │    - Suggests fallback intent                        │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     │                                       │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 3. Response Generation                               │  │
│  │    - intent: Classified intent code                  │  │
│  │    - confidence: Score (0.0-1.0)                     │  │
│  │    - extracted_entities: Parsed data                 │  │
│  │    - suggested_agent: Agent to route to              │  │
│  │    - fallback_intent: Alternative if primary fails   │  │
│  └──────────────────┬───────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Route to Appropriate Agent                                  │
│  - MemberVerificationAgent                                  │
│  - DeductibleOOPAgent                                       │
│  - BenefitAccumulatorAgent                                  │
│  - BenefitCoverageRAGAgent                                  │
│  - LocalRAGAgent                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Usage

### Basic Usage

```python
from MBA.agents import IntentIdentificationAgent

# Initialize agent
agent = IntentIdentificationAgent()

# Classify a single query
result = await agent.identify("Is member M1001 active?")

print(result)
# {
#     "success": True,
#     "intent": "member_verification",
#     "confidence": 0.95,
#     "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
#     "extracted_entities": {
#         "member_id": "M1001",
#         "query_type": "status"
#     },
#     "suggested_agent": "MemberVerificationAgent",
#     "fallback_intent": "general_inquiry",
#     "pattern_matches": {...},
#     "query": "Is member M1001 active?"
# }
```

### Batch Classification

```python
# Classify multiple queries
queries = [
    "Is member M1001 active?",
    "What is the deductible for member M1234?",
    "How many massage visits has member M5678 used?"
]

results = await agent.classify_batch(queries)

for result in results:
    print(f"Intent: {result['intent']} (Confidence: {result['confidence']})")
```

### Integration with Routing Logic

```python
async def handle_user_query(user_query: str):
    # Identify intent
    intent_agent = IntentIdentificationAgent()
    result = await intent_agent.identify(user_query)

    if not result.get("success"):
        return {"error": "Intent identification failed"}

    # Route to appropriate agent
    intent = result["intent"]
    entities = result["extracted_entities"]

    if intent == "member_verification":
        from MBA.agents import MemberVerificationAgent
        agent = MemberVerificationAgent()
        member_id = entities.get("member_id")
        return await agent.verify_member(member_id=member_id)

    elif intent == "deductible_oop":
        from MBA.agents import DeductibleOOPAgent
        agent = DeductibleOOPAgent()
        member_id = entities.get("member_id")
        return await agent.get_deductible_oop(member_id=member_id)

    elif intent == "benefit_accumulator":
        from MBA.agents import BenefitAccumulatorAgent
        agent = BenefitAccumulatorAgent()
        member_id = entities.get("member_id")
        return await agent.get_benefit_accumulator(member_id=member_id)

    elif intent == "benefit_coverage_rag":
        from MBA.agents import BenefitCoverageRAGAgent
        agent = BenefitCoverageRAGAgent()
        return await agent.query(question=user_query)

    elif intent == "local_rag":
        from MBA.agents import LocalRAGAgent
        agent = LocalRAGAgent()
        return await agent.query(question=user_query)

    else:  # general_inquiry
        return {
            "message": "I can help you with member verification, benefit inquiries, and more. What would you like to know?"
        }
```

---

## Response Structure

### Success Response

```json
{
  "success": true,
  "intent": "benefit_accumulator",
  "confidence": 0.98,
  "reasoning": "Detected member ID: M1234. Detected service type: massage therapy. Pattern matches: 3 for benefit_accumulator",
  "extracted_entities": {
    "member_id": "M1234",
    "service_type": "massage therapy",
    "query_type": "usage_count"
  },
  "suggested_agent": "BenefitAccumulatorAgent",
  "fallback_intent": "deductible_oop",
  "pattern_matches": {
    "member_verification": 1,
    "deductible_oop": 0,
    "benefit_accumulator": 3,
    "benefit_coverage_rag": 0,
    "local_rag": 0,
    "general_inquiry": 0
  },
  "query": "How many massage visits has member M1234 used?"
}
```

### Error Response

```json
{
  "success": false,
  "error": "Intent identification failed: Query cannot be empty",
  "intent": "general_inquiry",
  "confidence": 0.0
}
```

---

## Classification Logic

### Member-Specific vs General Questions

- **With Member ID** → `member_verification`, `deductible_oop`, or `benefit_accumulator`
- **Without Member ID** → `benefit_coverage_rag` or `local_rag`

### Financial vs Service Usage

- **Money/costs/payments** → `deductible_oop`
- **Visit counts/service limits** → `benefit_accumulator`

### Policy vs Personal

- **"Is X covered in general?"** → `benefit_coverage_rag`
- **"Has member M1001 used X service?"** → `benefit_accumulator`

### Confidence Levels

- **High (0.8-1.0)**: Clear indicators present, high certainty
- **Medium (0.5-0.79)**: Some ambiguity, likely intent is clear
- **Low (0.0-0.49)**: Very unclear, defaults to `general_inquiry`

---

## Pattern Matching

The agent uses regex patterns for fast pre-classification:

```python
INTENT_PATTERNS = {
    "member_verification": [
        r'\bmember\s+(?:id\s+)?[mM]\d+',
        r'\bverify\s+member',
        r'\bmember\s+status',
        r'\bmember\s+eligibility'
    ],
    "deductible_oop": [
        r'\bdeductible',
        r'\bout[-\s]of[-\s]pocket',
        r'\boop\b'
    ],
    "benefit_accumulator": [
        r'\bhow\s+many\s+(?:visits|sessions)',
        r'\bvisit\s+count',
        r'\bvisit\s+limit'
    ],
    # ... more patterns
}
```

---

## Entity Extraction

### Extracted Entities

| Entity | Description | Example |
|--------|-------------|---------|
| `member_id` | Member identifier | M1001, M1234 |
| `service_type` | Benefit service type | massage therapy, chiropractic |
| `query_type` | Type of query | status, coverage, usage_count, financial |

### Extraction Logic

```python
# Member ID extraction
Pattern: r'\b[mM](\d{3,})\b'
Example: "member M1001" → "M1001"

# Service type extraction
Keywords: massage therapy, chiropractic, acupuncture, etc.
Example: "massage therapy visits" → "massage therapy"

# Query type inference
- "status", "active" → "status"
- "coverage", "covered" → "coverage"
- "how many", "count" → "usage_count"
- "deductible", "paid" → "financial"
```

---

## Testing

### Unit Test Example

```python
import pytest
from MBA.agents import IntentIdentificationAgent

@pytest.mark.asyncio
async def test_member_verification_intent():
    agent = IntentIdentificationAgent()

    result = await agent.identify("Is member M1001 active?")

    assert result["success"] == True
    assert result["intent"] == "member_verification"
    assert result["confidence"] > 0.8
    assert result["extracted_entities"]["member_id"] == "M1001"

@pytest.mark.asyncio
async def test_benefit_accumulator_intent():
    agent = IntentIdentificationAgent()

    result = await agent.identify("How many massage visits has member M1234 used?")

    assert result["intent"] == "benefit_accumulator"
    assert result["extracted_entities"]["member_id"] == "M1234"
    assert result["extracted_entities"]["service_type"] == "massage therapy"
```

### Sample Test Queries

```python
test_queries = {
    "member_verification": [
        "Is member M1001 active?",
        "Check eligibility for member M5678",
        "Verify member status for ID M9999"
    ],
    "deductible_oop": [
        "What is the deductible for member M1001?",
        "Show OOP information for M1234",
        "Has member M5678 met their deductible?"
    ],
    "benefit_accumulator": [
        "How many massage visits has member M1001 used?",
        "Check chiropractic visit count for M1234",
        "What are the benefit limits for member M5678?"
    ],
    "benefit_coverage_rag": [
        "Is acupuncture covered?",
        "What are the copays for emergency room visits?",
        "Tell me about preventive care benefits"
    ],
    "local_rag": [
        "What does the uploaded document say about massage therapy?",
        "Search the benefit PDF for acupuncture coverage"
    ],
    "general_inquiry": [
        "Hello",
        "What can you help me with?",
        "How do I use this system?"
    ]
}
```

---

## Performance

- **Average Latency**: ~500-1000ms (includes pattern matching + entity extraction)
- **Pattern Matching**: < 10ms (very fast)
- **Entity Extraction**: < 50ms
- **Confidence Calculation**: < 10ms
- **Total Processing**: ~1 second per query

---

## Error Handling

The agent provides graceful error handling:

```python
# Empty query
result = await agent.identify("")
# Returns: {"success": False, "error": "Query is required", "intent": "general_inquiry"}

# Agent initialization failure
# Returns: {"success": False, "error": "Intent service unavailable", "confidence": 0.0}

# Unexpected errors
# Returns: {"success": False, "error": "Intent identification failed: ...", "intent": "general_inquiry"}
```

---

## Configuration

### Environment Variables

- `AWS_ACCESS_KEY_ID`: AWS credentials for Bedrock
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_DEFAULT_REGION`: AWS region (default: us-east-1)
- `BEDROCK_MODEL_ID`: Claude model ID (default: anthropic.claude-sonnet-4-20250514-v1:0)

### Model Configuration

The agent uses AWS Bedrock Claude Sonnet 4.5 for complex queries where pattern matching alone is insufficient.

---

## Limitations

1. **Member ID Format**: Only detects M followed by 3+ digits (e.g., M1001)
2. **Service Types**: Limited to predefined service keywords
3. **Context Awareness**: Doesn't maintain conversation history
4. **Language Support**: English only
5. **Confidence Thresholds**: Fixed thresholds may not suit all use cases

---

## Future Enhancements

- [ ] Multi-turn conversation support
- [ ] Context-aware classification using conversation history
- [ ] Support for additional member ID formats
- [ ] Expandable service type dictionary
- [ ] Confidence threshold tuning per intent
- [ ] Multi-language support
- [ ] Intent disambiguation for ambiguous queries
- [ ] Active learning from user feedback

---

## API Reference

### IntentIdentificationAgent Class

#### Methods

- `async identify(query: str, context: Optional[Dict] = None) -> Dict`: Classify single query
- `async classify_batch(queries: List[str], context: Optional[Dict] = None) -> List[Dict]`: Classify multiple queries
- `get_supported_intents() -> List[str]`: Get list of valid intent codes
- `get_agent_mapping() -> Dict[str, str]`: Get intent-to-agent mapping

---

## Troubleshooting

### Issue: Low Confidence Scores

**Solution**: Query may be ambiguous. Try:
- Adding more specific keywords (member ID, service type)
- Rephrasing query with clearer intent
- Checking extracted entities for correctness

### Issue: Wrong Intent Classification

**Solution**: Review pattern matches in response. If patterns don't match expected intent, consider:
- Adding new patterns to `INTENT_PATTERNS`
- Adjusting confidence calculation logic
- Providing more context in query

### Issue: Missing Entity Extraction

**Solution**: Entity extraction depends on regex patterns. If entities aren't detected:
- Check member ID format (must be M + digits)
- Verify service type is in predefined list
- Add custom extraction patterns if needed

---

## Support

For issues or questions:
- Review logs for detailed error messages
- Check AWS Bedrock credentials and permissions
- Verify model ID is correct
- Ensure network connectivity to AWS services

---

**Built with AWS Bedrock and Strands Agent SDK**
**Version**: 1.0.0
**Last Updated**: 2025-10-15
