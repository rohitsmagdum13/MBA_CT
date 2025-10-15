# Orchestration Agent Test Queries

Comprehensive list of test queries organized by intent type.

---

## 1. Member Verification Queries

### Basic Verification
```
Is member M1001 active?
Check if member M1002 is eligible
Verify member M1003
Is M1004 a valid member?
What is the status of member M1001?
Is member M1002 enrolled?
Check enrollment for M1003
```

### With Date of Birth
```
Verify member M1001 with DOB 2005-05-23
Check member with date of birth 1990-01-01
```

### With Name
```
Is Brandi Kim an active member?
Verify member John Smith
```

**Expected Intent**: `member_verification`
**Expected Agent**: `MemberVerificationAgent`

---

## 2. Deductible/OOP Queries

### Deductible Queries
```
What is the deductible for member M1001?
Show deductible information for M1002
Get deductible for M1003
How much has member M1001 paid towards their deductible?
```

### Out-of-Pocket Queries
```
What is the out-of-pocket max for member M1001?
Show OOP information for M1002
What's the out of pocket maximum for M1003?
What's remaining on M1002's out-of-pocket max?
```

### Combined Deductible/OOP
```
Show me deductible and OOP for member M1001
What are the cost-sharing amounts for M1002?
Get financial information for member M1003
```

**Expected Intent**: `deductible_oop`
**Expected Agent**: `DeductibleOOPAgent`

---

## 3. Benefit Accumulator Queries

### Service Usage
```
How many massage visits has member M1001 used?
Show massage therapy usage for M1002
How many chiropractic visits has M1003 used?
Massage visits for M1001
Chiropractic usage for M1002
Acupuncture count for M1003
Physical therapy visits for M1004
```

### Remaining Benefits
```
How many massage visits does M1001 have remaining?
What's left for acupuncture for member M1002?
Show remaining physical therapy visits for M1003
```

### Service Limits
```
What is the limit for massage therapy for M1001?
How many PT visits are allowed for M1002?
```

### All Benefits
```
Show all benefit usage for member M1001
What services has M1002 used?
Get benefit accumulator for M1003
```

**Expected Intent**: `benefit_accumulator`
**Expected Agent**: `BenefitAccumulatorAgent`

---

## 4. Benefit Coverage RAG Queries

### Coverage Questions
```
What is covered under massage therapy?
Is acupuncture covered?
What services are included in the benefit plan?
What benefits are covered?
Explain the benefit coverage
What does the plan cover?
```

### Policy Questions
```
What are the coverage limits for chiropractic care?
Tell me about the massage therapy benefit
What's the policy on physical therapy?
```

### Requirements & Restrictions
```
Do I need prior authorization for massage?
Are there any restrictions on chiropractic care?
What are the requirements for acupuncture coverage?
```

**Expected Intent**: `benefit_coverage_rag`
**Expected Agent**: `BenefitCoverageRAGAgent`

---

## 5. Local RAG Queries

### Document Queries
```
What does the uploaded document say about benefits?
Search uploaded files for coverage information
Query my documents about massage therapy
Find information in uploaded PDFs
What's in my benefit documents?
```

**Expected Intent**: `local_rag`
**Expected Agent**: `LocalRAGAgent`

---

## 6. General Inquiry Queries

### Greetings
```
Hello
Hi there
Hey
```

### Help Requests
```
What can you do?
Help me
What are your capabilities?
```

### General Questions
```
How does this work?
What is this system?
Tell me about MBA
```

**Expected Intent**: `general_inquiry`
**Expected Agent**: `OrchestrationAgent`

---

## 7. Edge Cases

### Missing Information
```
What is the deductible?
How many visits?
Check eligibility
```
*Should return error asking for member ID*

### Invalid Member IDs
```
Is member XYZ123 active?
Check member ABC
```
*May return error or attempt verification*

### Ambiguous Queries
```
Tell me about member M1001
M1001 information
```
*Should classify to most likely intent based on context*

### Multiple Intents
```
Is member M1001 active and what's their deductible?
Check M1002 eligibility and show massage usage
```
*Should route to first detected intent*

### Typos and Variations
```
membr M1001
dedcutible for M1002
masage visits M1003
```
*Should handle gracefully with fuzzy matching*

---

## 8. Complex Queries

### Long Queries
```
I need to verify if member M1001 is currently active and enrolled in the system, and also check their eligibility status
```

### Multiple Data Points
```
For member M1001 with date of birth 2005-05-23, verify their status and show me their benefit information
```

### Natural Language Variations
```
Can you tell me whether or not the member with ID M1001 has active coverage?
I'd like to know about member M1002's deductible and out-of-pocket expenses
Could you please check how many massage therapy sessions member M1003 has used so far this year?
```

---

## How to Test

### Quick Test (5 queries, one per intent)
```bash
python test_all_orchestration_queries.py --quick
```

### Full Test Suite (100+ queries)
```bash
python test_all_orchestration_queries.py
```

### Single Query Test
```bash
python test_orchestration_fix.py
```

### API Test
```bash
# Start the API
python -m src.MBA.microservices.api

# Test with curl
curl -X POST "http://localhost:8000/orchestrate/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "Is member M1001 active?"}'
```

### Streamlit UI Test
```bash
streamlit run src/MBA/ui/streamlit_app.py
```
Then navigate to **Tab 11: AI Orchestration**

---

## Expected Response Format

All queries should return:
```json
{
  "success": true/false,
  "intent": "member_verification|deductible_oop|benefit_accumulator|benefit_coverage_rag|local_rag|general_inquiry",
  "agent": "MemberVerificationAgent|DeductibleOOPAgent|BenefitAccumulatorAgent|...",
  "confidence": 0.0-1.0,
  "result": {
    // Agent-specific result data
  },
  "reasoning": "Why this intent was chosen",
  "extracted_entities": {
    "member_id": "M1001",
    "service_type": "massage",
    // etc.
  },
  "query": "Original query text"
}
```

---

## Success Criteria

✅ **Intent Classification**: Query should be classified to correct intent
✅ **Entity Extraction**: Member IDs, service types, etc. should be extracted
✅ **Agent Routing**: Correct specialized agent should be called
✅ **Result Capture**: Agent results should be captured and returned
✅ **Error Handling**: Errors should be gracefully handled with helpful messages
✅ **Confidence Score**: Should reflect classification certainty
✅ **No Parse Errors**: No "Failed to parse agent response" errors

---

## Member IDs in Test Data

Valid member IDs in the database:
- **M1001** - Brandi Kim (DOB: 2005-05-23)
- **M1002** - Dawn Brown (DOB: 1961-04-08)
- **M1003** - Kathleen Clark (DOB: 1964-04-13)
- **M1004** - Jeffrey Hill (DOB: 1999-05-14)
- **M1005** - Justin Moore (DOB: 1969-10-20)

Use these for testing member verification, deductible/OOP, and benefit accumulator queries.

---

## Service Types for Benefit Accumulator

Valid service types:
- `massage` / `massage therapy`
- `chiropractic` / `chiropractor`
- `acupuncture`
- `physical therapy` / `PT`

---

## Notes

- Some queries may intentionally fail (e.g., missing member ID) - this is expected behavior
- Edge cases test error handling and robustness
- Complex queries test natural language understanding
- Typo queries test fuzzy matching and error tolerance
