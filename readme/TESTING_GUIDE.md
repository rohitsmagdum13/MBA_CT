# Orchestration Agent Testing Guide

Complete guide for testing the orchestration agent with all available tools and test queries.

---

## 🚀 Quick Start

### 1. Interactive Testing (Recommended for Manual Testing)
```bash
python interactive_orchestration_test.py
```

Interactive console where you can:
- Type queries one at a time
- See formatted results instantly
- View examples with `examples` command
- Toggle JSON output with `json` command
- Type `quit` to exit

### 2. Quick Test (5 queries, one per intent)
```bash
python test_all_orchestration_queries.py --quick
```

Tests one query from each intent type:
- Member Verification
- Deductible/OOP
- Benefit Accumulator
- Benefit Coverage RAG
- General Inquiry

### 3. Full Test Suite (100+ queries)
```bash
python test_all_orchestration_queries.py
```

Comprehensive test with:
- All query types and variations
- Edge cases and error handling
- Detailed results saved to `orchestration_test_results.json`
- Summary statistics and breakdowns

### 4. Single Query Test
```bash
python test_orchestration_fix.py
```

Simple test with one hardcoded query to verify the fix works.

---

## 📝 Test Files Overview

### Test Scripts

| File | Purpose | Usage |
|------|---------|-------|
| **interactive_orchestration_test.py** | Interactive console for manual testing | `python interactive_orchestration_test.py` |
| **test_all_orchestration_queries.py** | Comprehensive automated test suite | `python test_all_orchestration_queries.py` |
| **test_orchestration_fix.py** | Simple single-query verification | `python test_orchestration_fix.py` |
| **test_orchestration_api.py** | API endpoint testing (if exists) | `python test_orchestration_api.py` |

### Reference Documents

| File | Contents |
|------|----------|
| **TEST_QUERIES.md** | Complete list of test queries organized by intent |
| **ORCHESTRATION_FIX.md** | Documentation of the response parsing fix |
| **TESTING_GUIDE.md** | This file - complete testing guide |

---

## 📋 Test Query Categories

### 1. Member Verification (11 queries)
Test member eligibility and enrollment status.

**Sample Queries:**
```
Is member M1001 active?
Verify member M1002
Check if member M1003 is eligible
```

**Expected:**
- Intent: `member_verification`
- Agent: `MemberVerificationAgent`
- Result includes: `valid`, `member_id`, `name`, `dob`, `status`

---

### 2. Deductible/OOP (10 queries)
Test deductible and out-of-pocket maximum queries.

**Sample Queries:**
```
What is the deductible for member M1001?
Show OOP information for M1002
What's the out of pocket maximum for M1003?
```

**Expected:**
- Intent: `deductible_oop`
- Agent: `DeductibleOOPAgent`
- Result includes: `found`, `member_id`, `deductible_amount`, `oop_max`, etc.

---

### 3. Benefit Accumulator (17 queries)
Test benefit usage tracking for various services.

**Sample Queries:**
```
How many massage visits has member M1001 used?
Show chiropractic usage for M1002
Massage visits for M1001
```

**Expected:**
- Intent: `benefit_accumulator`
- Agent: `BenefitAccumulatorAgent`
- Result includes: `found`, `member_id`, `service`, `used_count`, `limit`, etc.

---

### 4. Benefit Coverage RAG (12 queries)
Test coverage policy questions using RAG.

**Sample Queries:**
```
What is covered under massage therapy?
Is acupuncture covered?
What are the coverage limits for chiropractic care?
```

**Expected:**
- Intent: `benefit_coverage_rag`
- Agent: `BenefitCoverageRAGAgent`
- Result includes: `answer`, `sources`, `confidence`

---

### 5. Local RAG (5 queries)
Test queries about uploaded documents.

**Sample Queries:**
```
What does the uploaded document say about benefits?
Search uploaded files for coverage information
```

**Expected:**
- Intent: `local_rag`
- Agent: `LocalRAGAgent`
- Result includes: `answer`, `sources`

---

### 6. General Inquiry (9 queries)
Test greetings and help requests.

**Sample Queries:**
```
Hello
What can you do?
Help me
```

**Expected:**
- Intent: `general_inquiry`
- Agent: `OrchestrationAgent`
- Result includes: capabilities message

---

### 7. Edge Cases (12 queries)
Test error handling and robustness.

**Sample Queries:**
```
What is the deductible?  (missing member ID)
Is member XYZ123 active?  (invalid member ID)
How many visits?  (ambiguous)
```

**Expected:**
- Graceful error handling
- Helpful error messages
- Request for missing information

---

### 8. Complex Queries (6 queries)
Test natural language understanding.

**Sample Queries:**
```
I need to verify if member M1001 is currently active and enrolled
Could you please check how many massage therapy sessions member M1003 has used so far this year?
```

**Expected:**
- Correct intent classification despite complex wording
- Entity extraction from long queries

---

## 🎯 Testing Methods

### Method 1: Interactive Console

**Best for:** Manual exploration and debugging

```bash
python interactive_orchestration_test.py
```

**Features:**
- Real-time query testing
- Formatted output
- Command support (`examples`, `history`, `json`)
- Easy to use

**Example Session:**
```
>>> Is member M1001 active?
⏳ Processing: Is member M1001 active?...

================================================================================
ORCHESTRATION RESULT
================================================================================

Status: ✅ SUCCESS

Intent: member_verification
Agent: MemberVerificationAgent
Confidence: 0.650

...
```

---

### Method 2: Batch Testing from Command Line

```bash
# Test specific queries
python interactive_orchestration_test.py "Is member M1001 active?" "What is the deductible for M1002?"

# Test queries from file
python interactive_orchestration_test.py --file my_queries.txt
```

---

### Method 3: Automated Test Suite

```bash
# Quick test
python test_all_orchestration_queries.py --quick

# Full test
python test_all_orchestration_queries.py
```

**Output includes:**
- Success/failure counts
- Intent classification breakdown
- Agent routing statistics
- Average confidence by intent
- Detailed failure analysis
- JSON results file

---

### Method 4: API Testing

```bash
# Start API server
python -m src.MBA.microservices.api

# Test with curl (in another terminal)
curl -X POST "http://localhost:8000/orchestrate/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Is member M1001 active?"}'

# Test batch
curl -X POST "http://localhost:8000/orchestrate/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "queries": [
      "Is member M1001 active?",
      "What is the deductible for M1002?"
    ]
  }'
```

---

### Method 5: Streamlit UI

```bash
streamlit run src/MBA/ui/streamlit_app.py
```

Navigate to **Tab 11: 🎯 AI Orchestration**

**Test modes:**
1. **Single Query** - Test individual queries with reasoning display
2. **Batch Queries** - Test multiple queries (manual or CSV upload)
3. **Conversation History** - View and manage session history

---

## 📊 Expected Response Format

Every orchestration query should return:

```json
{
  "success": true,
  "intent": "member_verification",
  "agent": "MemberVerificationAgent",
  "confidence": 0.65,
  "result": {
    "valid": true,
    "member_id": "M1001",
    "name": "Brandi Kim",
    "dob": "2005-05-23",
    "status": "Active"
  },
  "reasoning": "Query contains member ID M1001 and asks about status/activity",
  "extracted_entities": {
    "member_id": "M1001"
  },
  "query": "Is member M1001 active?"
}
```

---

## ✅ Success Criteria

For each test query:

- [ ] **No Parse Errors**: No "Failed to parse agent response" errors
- [ ] **Correct Intent**: Query classified to expected intent
- [ ] **Entity Extraction**: Member IDs, services, etc. properly extracted
- [ ] **Agent Routing**: Correct specialized agent invoked
- [ ] **Result Capture**: Agent results properly returned
- [ ] **Error Handling**: Graceful handling of errors with helpful messages
- [ ] **Confidence Score**: Reasonable confidence value (typically 0.4-1.0)
- [ ] **Success Flag**: Properly set based on actual success/failure

---

## 🔍 Debugging Failed Tests

If a test fails, check:

1. **Logs**: Look for detailed logs showing tool execution
   ```
   Tool #1: analyze_query
   Tool #2: route_to_agent
   ```

2. **Intent Classification**: Was the intent correctly identified?
   - Check confidence score
   - Review reasoning field

3. **Entity Extraction**: Were entities properly extracted?
   - Check extracted_entities field
   - Verify member IDs, service types

4. **Agent Execution**: Did the specialized agent run?
   - Check agent field
   - Look for agent-specific logs

5. **Error Messages**: What error was returned?
   - Missing member ID?
   - Database issue?
   - Invalid parameters?

---

## 📈 Performance Benchmarks

Expected performance metrics:

| Metric | Target | Notes |
|--------|--------|-------|
| Intent Accuracy | >85% | Correct intent classification |
| Entity Extraction | >90% | Correct member ID/service extraction |
| Success Rate | >80% | Queries return success=true |
| Avg Response Time | <5s | Including database queries |
| Avg Confidence | >0.60 | For successful classifications |

---

## 🧪 Test Data

### Valid Member IDs
```
M1001 - Brandi Kim (DOB: 2005-05-23)
M1002 - Dawn Brown (DOB: 1961-04-08)
M1003 - Kathleen Clark (DOB: 1964-04-13)
M1004 - Jeffrey Hill (DOB: 1999-05-14)
M1005 - Justin Moore (DOB: 1969-10-20)
```

### Valid Service Types
```
massage, massage therapy
chiropractic, chiropractor
acupuncture
physical therapy, PT
```

---

## 🐛 Known Issues

1. **Strands Framework Limitation**: Response objects don't capture tool results
   - **Fix**: Using global cache workaround
   - **Status**: ✅ Resolved

2. **Parameter Name Mismatch**: `service_type` vs `service`
   - **Fix**: Updated to use `service` parameter
   - **Status**: ✅ Resolved

3. **Intent Misclassification**: Usage queries misclassified as member verification
   - **Fix**: Added special handling for "how many", "count", "used" keywords
   - **Status**: ✅ Resolved

---

## 📞 Need Help?

- **Documentation**: See [ORCHESTRATION_FIX.md](ORCHESTRATION_FIX.md) for fix details
- **Query Reference**: See [TEST_QUERIES.md](TEST_QUERIES.md) for all test queries
- **Source Code**: See [src/MBA/agents/orchestration_agent/](src/MBA/agents/orchestration_agent/)

---

## 🎉 Quick Test Commands Cheat Sheet

```bash
# Interactive testing (recommended)
python interactive_orchestration_test.py

# Quick automated test
python test_all_orchestration_queries.py --quick

# Full automated test
python test_all_orchestration_queries.py

# Single query verification
python test_orchestration_fix.py

# API test
curl -X POST "http://localhost:8000/orchestrate/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Is member M1001 active?"}'

# Streamlit UI
streamlit run src/MBA/ui/streamlit_app.py
```

Happy Testing! 🚀
