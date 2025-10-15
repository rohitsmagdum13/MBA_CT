# Intent Identification Agent - Quick Reference

## 🚀 Quick Start

```python
from MBA.agents import IntentIdentificationAgent

agent = IntentIdentificationAgent()
result = await agent.identify("Is member M1001 active?")
print(result["intent"])  # "member_verification"
```

## 📋 Intent Categories

| Code | Purpose | Example |
|------|---------|---------|
| `member_verification` | Check member status | "Is member M1001 active?" |
| `deductible_oop` | Financial queries | "What is the deductible for M1001?" |
| `benefit_accumulator` | Service usage | "How many massage visits for M1001?" |
| `benefit_coverage_rag` | Policy questions | "Is acupuncture covered?" |
| `local_rag` | Document queries | "What does the PDF say about massage?" |
| `general_inquiry` | Help/greetings | "Hello, what can you do?" |

## 🎯 Classification Rules

### With Member ID → `member_verification`, `deductible_oop`, or `benefit_accumulator`
- "Is member **M1001** active?" → member_verification
- "What is the deductible for **M1234**?" → deductible_oop
- "How many visits for **M5678**?" → benefit_accumulator

### Without Member ID → `benefit_coverage_rag` or `local_rag`
- "Is acupuncture covered?" → benefit_coverage_rag
- "Search the document" → local_rag

## 💡 Response Fields

```json
{
  "success": true,
  "intent": "intent_code",
  "confidence": 0.95,
  "reasoning": "explanation",
  "extracted_entities": {
    "member_id": "M1001",
    "service_type": "massage therapy",
    "query_type": "usage_count"
  },
  "suggested_agent": "AgentName",
  "fallback_intent": "alternative"
}
```

## 🧪 Test It

```bash
python test_intent_agent.py
```

## 📚 Full Docs

See `src/MBA/agents/intent_identification_agent/README.md`
