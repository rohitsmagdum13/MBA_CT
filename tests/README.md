# MBA Tests

This directory contains all test files for the MBA (Member Benefit Assistant) system, organized by agent.

## Structure

```
tests/
├── intent_agent/              # Tests for Intent Identification Agent
│   ├── test_intent_agent.py   # Unit tests for intent classification
│   └── test_intent_api.py     # API endpoint tests
├── orchestration_agent/       # Tests for Orchestration Agent
│   └── test_orchestration_api.py  # API endpoint tests
└── verification_agent/        # Tests for Member Verification Agent
    └── test_verification.py   # API endpoint tests
```

## Running Tests

### Intent Identification Agent Tests

**Unit Tests:**
```bash
python tests/intent_agent/test_intent_agent.py
```

**API Tests:**
```bash
# Start API server first
python -m MBA.microservices.api

# Run tests in another terminal
python tests/intent_agent/test_intent_api.py
```

### Orchestration Agent Tests

```bash
# Start API server first
python -m MBA.microservices.api

# Run tests in another terminal
python tests/orchestration_agent/test_orchestration_api.py
```

### Member Verification Agent Tests

```bash
# Start API server first
python -m MBA.microservices.api

# Run tests in another terminal
python tests/verification_agent/test_verification.py
```

## Test Coverage

### Intent Agent
- ✓ Single query classification
- ✓ Batch query classification
- ✓ Entity extraction
- ✓ Edge case handling
- ✓ API endpoint validation

### Orchestration Agent
- ✓ Query routing
- ✓ Agent selection
- ✓ Batch processing
- ✓ Conversation history
- ✓ Error handling

### Verification Agent
- ✓ Single member verification
- ✓ Batch member verification
- ✓ Health check validation
