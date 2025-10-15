# Orchestration Agent

## Overview

The **Orchestration Agent** is the central routing and coordination layer for the MBA (Member Benefits Assistant) system. It provides intelligent query routing, multi-agent orchestration, and unified response handling across all specialized agents in the system.

## Architecture

```
User Query
    ↓
Orchestration Agent
    ↓
Intent Identification Agent (classify intent)
    ↓
Route to Specialized Agent:
    ├─ Member Verification Agent
    ├─ Deductible/OOP Agent
    ├─ Benefit Accumulator Agent
    ├─ Benefit Coverage RAG Agent
    └─ Local RAG Agent
    ↓
Unified Response
```

## Key Features

### 1. Intelligent Query Routing
- Automatically identifies user intent using the Intent Identification Agent
- Routes queries to the appropriate specialized agent based on classification
- Supports confidence-based fallback strategies

### 2. Multi-Agent Coordination
- Seamlessly orchestrates across 6 specialized agents
- Handles complex workflows requiring multiple agent interactions
- Provides unified response format across all agents

### 3. Conversation Context Management
- Optional conversation history tracking
- Context-aware query processing
- Session management for multi-turn interactions

### 4. Error Handling & Fallback
- Comprehensive error handling at each orchestration step
- Graceful degradation when agents are unavailable
- Informative error messages for debugging

### 5. Batch Processing
- Process multiple queries simultaneously
- Efficient batch orchestration for analytics and testing
- Intent distribution analysis across query batches

## Components

### `wrapper.py`
The main Orchestration Agent class that implements:
- **`process_query()`**: Process single query with automatic routing
- **`process_batch()`**: Process multiple queries in batch
- **`get_conversation_history()`**: Retrieve conversation history
- **`clear_conversation_history()`**: Clear session history
- **`get_available_agents()`**: List all available agents

### `__init__.py`
Package initialization and exports for the orchestration agent module.

## Supported Agents

The Orchestration Agent can route to the following specialized agents:

| Intent | Agent | Capabilities |
|--------|-------|--------------|
| `member_verification` | MemberVerificationAgent | Member eligibility, status, identity validation |
| `deductible_oop` | DeductibleOOPAgent | Deductible and out-of-pocket information |
| `benefit_accumulator` | BenefitAccumulatorAgent | Benefit usage tracking, service limits |
| `benefit_coverage_rag` | BenefitCoverageRAGAgent | Coverage policy questions (RAG) |
| `local_rag` | LocalRAGAgent | User-uploaded document queries (RAG) |
| `general_inquiry` | OrchestrationAgent | Greetings, general help |

## Usage

### Python API

```python
from MBA.agents import OrchestrationAgent

# Initialize orchestration agent
agent = OrchestrationAgent()

# Process a single query (automatic routing)
result = await agent.process_query("Is member M1001 active?")

print(f"Intent: {result['intent']}")
print(f"Agent: {result['agent']}")
print(f"Success: {result['success']}")
print(f"Result: {result['result']}")

# Process batch queries
queries = [
    "Is member M1001 active?",
    "What is the deductible for member M1234?",
    "How many massage visits has member M5678 used?"
]
results = await agent.process_batch(queries)

# Manage conversation history
result = await agent.process_query(
    "Is member M1001 active?",
    preserve_history=True
)
history = agent.get_conversation_history()
agent.clear_conversation_history()
```

### REST API Endpoints

#### 1. Process Single Query
```bash
POST /orchestrate/query
```

**Request:**
```json
{
    "query": "Is member M1001 active?",
    "context": {},
    "preserve_history": false
}
```

**Response:**
```json
{
    "success": true,
    "intent": "member_verification",
    "confidence": 0.95,
    "agent": "MemberVerificationAgent",
    "result": {
        "valid": true,
        "member_id": "M1001",
        "name": "John Doe",
        "dob": "1990-01-01",
        "status": "active"
    },
    "query": "Is member M1001 active?",
    "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
    "extracted_entities": {
        "member_id": "M1001",
        "query_type": "status"
    }
}
```

#### 2. Process Batch Queries
```bash
POST /orchestrate/batch
```

**Request:**
```json
{
    "queries": [
        "Is member M1001 active?",
        "What is the deductible for member M1234?",
        "How many massage visits has member M5678 used?"
    ],
    "context": {}
}
```

**Response:**
```json
{
    "results": [...],
    "total": 3,
    "successful": 3,
    "failed": 0,
    "intents": {
        "member_verification": 1,
        "deductible_oop": 1,
        "benefit_accumulator": 1
    }
}
```

#### 3. Get Available Agents
```bash
GET /orchestrate/agents
```

**Response:**
```json
{
    "agents": [
        "IntentIdentificationAgent",
        "MemberVerificationAgent",
        "DeductibleOOPAgent",
        "BenefitAccumulatorAgent",
        "BenefitCoverageRAGAgent",
        "LocalRAGAgent"
    ],
    "total_agents": 6,
    "orchestration_enabled": true
}
```

#### 4. Get Conversation History
```bash
GET /orchestrate/history
```

**Response:**
```json
{
    "history": [
        {
            "query": "Is member M1001 active?",
            "intent": "member_verification",
            "confidence": 0.95,
            "agent": "MemberVerificationAgent",
            "success": true,
            "timestamp": null
        }
    ],
    "total_interactions": 1
}
```

#### 5. Clear Conversation History
```bash
DELETE /orchestrate/history
```

**Response:**
```json
{
    "success": true,
    "message": "Conversation history cleared"
}
```

## Query Examples

### Member Verification
```
"Is member M1001 active?"
"Check eligibility for member M1234"
"Verify John Doe born 1990-01-01"
```
→ Routes to **MemberVerificationAgent**

### Deductible/OOP
```
"What is the deductible for member M1001?"
"How much is the out-of-pocket max?"
"Member M1234 wants to know their deductible"
```
→ Routes to **DeductibleOOPAgent**

### Benefit Accumulator
```
"How many massage visits has member M1001 used?"
"Check PT visit usage for M1234"
"Remaining chiropractic visits for M5678"
```
→ Routes to **BenefitAccumulatorAgent**

### Coverage Questions
```
"Is acupuncture covered under the plan?"
"Does the plan cover dental implants?"
"What are the massage therapy benefits?"
```
→ Routes to **BenefitCoverageRAGAgent**

### General Inquiries
```
"Hello, can you help me?"
"What can you do?"
"Thank you!"
```
→ Handled by **OrchestrationAgent**

## Testing

### Run API Server
```bash
python -m MBA.microservices.api
```

### Run Orchestration Tests
```bash
python test_orchestration_api.py
```

The test suite validates:
- ✅ Health check and initialization
- ✅ Available agents listing
- ✅ Single query orchestration (5 intent types)
- ✅ Batch query processing
- ✅ Conversation history management
- ✅ Error handling (empty queries, missing fields)
- ✅ Routing accuracy (8 diverse queries)

## Response Format

All orchestration responses follow a unified format:

```json
{
    "success": bool,           // Operation success status
    "intent": str,             // Classified intent
    "confidence": float,       // Intent confidence (0.0-1.0)
    "agent": str,              // Agent that processed the query
    "result": {...},           // Agent-specific result
    "query": str,              // Original query
    "reasoning": str,          // Intent classification reasoning
    "extracted_entities": {...}, // Extracted entities (member_id, etc.)
    "error": str               // Error message (if applicable)
}
```

## Error Handling

The Orchestration Agent handles errors at multiple levels:

1. **Query Validation**: Empty or invalid queries
2. **Intent Classification**: Fallback to general_inquiry if classification fails
3. **Agent Routing**: Informative errors for missing required parameters
4. **Agent Execution**: Graceful error handling from specialized agents
5. **Response Building**: Structured error responses with full context

## Performance Considerations

- **Lazy Initialization**: Agents are initialized on first use
- **Async Processing**: Full async/await support for non-blocking operations
- **Batch Optimization**: Efficient processing of multiple queries
- **Error Isolation**: Individual query failures don't affect batch processing

## Integration Patterns

### 1. Chatbot/Virtual Assistant
```python
agent = OrchestrationAgent()

while True:
    user_query = get_user_input()
    result = await agent.process_query(
        query=user_query,
        preserve_history=True
    )
    display_response(result)
```

### 2. API Gateway
```python
@app.post("/chat")
async def chat_endpoint(query: str):
    agent = OrchestrationAgent()
    result = await agent.process_query(query)
    return result
```

### 3. Batch Analytics
```python
agent = OrchestrationAgent()
queries = load_queries_from_file()
results = await agent.process_batch(queries)
analyze_intent_distribution(results)
```

## Future Enhancements

Potential improvements for the Orchestration Agent:

- [ ] Multi-agent workflows (sequential agent execution)
- [ ] Context-aware routing (use conversation history for better classification)
- [ ] Agent health monitoring and circuit breakers
- [ ] Response caching for frequently asked questions
- [ ] A/B testing for routing strategies
- [ ] Metrics and observability (latency, success rates, etc.)
- [ ] Dynamic agent registration/discovery
- [ ] Weighted voting for multi-agent consensus

## Dependencies

- AWS Bedrock (via IntentIdentificationAgent)
- All specialized MBA agents
- Python 3.9+
- FastAPI (for API endpoints)

## Version History

- **v1.0.0** (2025-10-15): Initial release
  - Single and batch query orchestration
  - 6 specialized agent integrations
  - Conversation history management
  - REST API endpoints
  - Comprehensive test suite

## Support

For issues or questions about the Orchestration Agent:
1. Check the test suite: `test_orchestration_api.py`
2. Review agent logs in the console output
3. Verify all agents are initialized in health check
4. Check intent classification results for debugging

## License

Part of the MBA (Member Benefits Assistant) system.
