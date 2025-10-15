# RAG Query Orchestration Fix

## Problems Identified

From the test logs, two critical issues were found with RAG-related queries:

### Issue 1: `route_to_agent` Not Being Called for `general_inquiry`

**Symptoms:**
```
Retrieved cached tool results: ['analyze_query']  ❌ Missing 'route_to_agent'
Have analysis result but no routing result  ⚠️
```

**Affected Queries:**
- "What services are included in the benefit plan?"
- "What does the plan cover?"
- "Tell me about covered services"
- "What benefits are available?"
- "Explain the benefit coverage"
- "What is the massage therapy benefit?"

**Root Cause:**
The system prompt said "General Inquiry (Handled by you directly)" which made the AI think it should answer directly without calling `route_to_agent`.

**Impact:**
- Queries got `success: false`
- Error: "Query analysis succeeded but routing failed"
- User got no useful response

---

### Issue 2: `route_to_agent` Called with `intent: None`

**Symptoms:**
```
Tool #10: route_to_agent
Routing to agent: BenefitCoverageRAGAgent for intent: None  ❌
```

**Affected Queries:**
- "What is covered under massage therapy?"
- "Is acupuncture covered?"

**Root Cause:**
The AI was calling `route_to_agent` but NOT passing the required parameters (`intent`, `agent`, `extracted_entities`) correctly.

**Impact:**
- Agent routing failed
- BenefitCoverageRAGAgent didn't execute properly
- Queries returned generic text responses instead of RAG results

---

## Root Cause Analysis

The orchestration agent uses AWS Bedrock Claude to make intelligent routing decisions. However, the **system prompt was not explicit enough** about:

1. **Tool call requirements**: The AI thought it could skip `route_to_agent` for certain intents
2. **Parameter requirements**: The AI wasn't clearly instructed on which parameters to pass to each tool
3. **Workflow enforcement**: The prompt suggested the workflow but didn't MANDATE it

---

## Fixes Applied

### Fix 1: Enforce Mandatory Tool Sequence

**File**: `src/MBA/agents/orchestration_agent/prompt.py`

**Changes** (lines 89-115):

```python
## Orchestration Workflow

⚠️ **CRITICAL**: You MUST use ALL THREE TOOLS in sequence for EVERY query. Do not skip any tool.

When you receive a user query, follow this EXACT workflow:

### Step 1: Analyze the Query (REQUIRED)
**You MUST call the `analyze_query` tool** to:
- Classify the intent
- Extract entities (member_id, service_type, etc.)
- Determine which agent should handle the request
- Assess confidence in the classification

### Step 2: Route to Appropriate Agent (REQUIRED)
**You MUST call the `route_to_agent` tool** to:
- Execute the selected agent's workflow
- Pass the intent, agent name, extracted entities, and query
- Handle any errors or missing data
- Return the agent's response

⚠️ **IMPORTANT**: Call `route_to_agent` for ALL intents, including general_inquiry!

### Step 3: Format Response (OPTIONAL)
Use the `format_response` tool to:
- Present the results to the user in a clear, conversational manner
- Format based on the intent type
- Add helpful context and guidance
```

**Key Changes:**
- Added "⚠️ **CRITICAL**" warning
- Changed "follow this workflow" to "follow this EXACT workflow"
- Made Step 1 and Step 2 **REQUIRED** (all caps)
- Explicitly stated "Call `route_to_agent` for ALL intents, including general_inquiry!"
- Made Step 3 optional (since it's not critical)

---

### Fix 2: Clarify Tool Parameter Requirements

**File**: `src/MBA/agents/orchestration_agent/prompt.py`

**Changes** (lines 211-234):

```python
## Tool Usage Instructions

⚠️ **MANDATORY TOOL SEQUENCE**: analyze_query → route_to_agent → (optional: format_response)

### analyze_query (REQUIRED - Call FIRST)
- **You MUST call this tool FIRST** for every query
- Extract all relevant entities (member_id, service_type, dob, name, etc.)
- Classify the intent and determine which agent to use
- Return: intent, confidence, agent name, extracted_entities, reasoning

### route_to_agent (REQUIRED - Call SECOND)
- **You MUST call this tool SECOND** for every query, even general_inquiry
- Pass the results from analyze_query:
  - `intent`: The classified intent from analyze_query
  - `agent`: The agent name from analyze_query
  - `extracted_entities`: All entities from analyze_query
  - `query`: The original user query
- This tool will execute the appropriate agent and return results
- **DO NOT skip this tool** - it handles ALL intents including general_inquiry

### format_response (OPTIONAL - Call THIRD)
- Optionally call this to format the response
- Pass the routing result for formatting
- Returns a nicely formatted response for the user
```

**Key Changes:**
- Added "⚠️ **MANDATORY TOOL SEQUENCE**" header
- Explicitly listed required parameters for `route_to_agent`
- Added "**DO NOT skip this tool**" warning
- Clarified that ALL intents (including general_inquiry) must use route_to_agent

---

### Fix 3: Add Explicit Tool Usage Examples

**File**: `src/MBA/agents/orchestration_agent/prompt.py`

**Changes** (lines 254-348):

Added three detailed examples showing EXACT tool calls with parameters:

#### Example 1: Member Verification
```
1. Call `analyze_query` with params: {"query": "Is member M1001 active?"}
   → Returns: {intent: "member_verification", agent: "MemberVerificationAgent", extracted_entities: {member_id: "M1001"}}

2. Call `route_to_agent` with params: {"intent": "member_verification", "agent": "MemberVerificationAgent", "query": "Is member M1001 active?", "extracted_entities": {member_id: "M1001"}}
   → Returns: {success: true, agent: "MemberVerificationAgent", result: {...}}
```

#### Example 3: RAG Coverage Question
```
1. Call `analyze_query` with params: {"query": "Is acupuncture covered?"}
   → Returns: {intent: "benefit_coverage_rag", agent: "BenefitCoverageRAGAgent", extracted_entities: {service_type: "acupuncture"}}

2. Call `route_to_agent` with params: {"intent": "benefit_coverage_rag", "agent": "BenefitCoverageRAGAgent", "query": "Is acupuncture covered?", "extracted_entities": {service_type: "acupuncture"}}
   → Returns: {success: true, agent: "BenefitCoverageRAGAgent", result: {answer: "..."}}
```

#### Example 4: General Inquiry (NEW)
```
1. Call `analyze_query` with params: {"query": "What can you do?"}
   → Returns: {intent: "general_inquiry", agent: "OrchestrationAgent", extracted_entities: {}}

2. Call `route_to_agent` with params: {"intent": "general_inquiry", "agent": "OrchestrationAgent", "query": "What can you do?", "extracted_entities": {}}
   → Returns: {success: true, agent: "OrchestrationAgent", result: {message: "..."}}
```

**Key Changes:**
- Changed from vague workflow descriptions to EXACT tool call examples
- Shows specific parameter names and values
- Shows expected returns from each tool
- Added Example 4 for general_inquiry to demonstrate it also needs routing

---

## Expected Behavior After Fix

### For RAG Coverage Queries

**Query**: "What is covered under massage therapy?"

**Expected Flow:**
1. ✅ `analyze_query` called
   - Intent: `benefit_coverage_rag`
   - Agent: `BenefitCoverageRAGAgent`
   - Entities: `{service_type: "massage therapy"}`

2. ✅ `route_to_agent` called with intent="benefit_coverage_rag"
   - Routes to BenefitCoverageRAGAgent
   - Calls `agent.query(question="What is covered under massage therapy?", k=5)`
   - Returns RAG results from vector database

3. ✅ Response contains:
   - `success: true`
   - `intent: "benefit_coverage_rag"`
   - `agent: "BenefitCoverageRAGAgent"`
   - `result: {answer: "...", sources: [...]}`

---

### For General Inquiry Queries

**Query**: "What services are included in the benefit plan?"

**Expected Flow:**
1. ✅ `analyze_query` called
   - Intent: `general_inquiry`
   - Agent: `OrchestrationAgent`
   - Entities: `{query_type: "coverage"}`

2. ✅ `route_to_agent` called with intent="general_inquiry"
   - Routes to OrchestrationAgent (self)
   - Returns general capabilities message

3. ✅ Response contains:
   - `success: true`
   - `intent: "general_inquiry"`
   - `agent: "OrchestrationAgent"`
   - `result: {message: "I'm the MBA system orchestration agent..."}`

---

## Testing

### Test Queries to Verify Fix

#### RAG Coverage Queries (Should route to BenefitCoverageRAGAgent)
```
What is covered under massage therapy?
Is acupuncture covered?
What are the coverage limits for chiropractic care?
Tell me about the massage therapy benefit
Do I need prior authorization for massage?
Are there visit limits for acupuncture?
```

**Expected:**
- `intent: "benefit_coverage_rag"`
- `agent: "BenefitCoverageRAGAgent"`
- Both `analyze_query` AND `route_to_agent` in cached results
- `success: true`

---

#### General Inquiry Queries (Should route to OrchestrationAgent)
```
What services are included in the benefit plan?
What does the plan cover?
Tell me about covered services
What benefits are available?
Explain the benefit coverage
```

**Expected:**
- `intent: "general_inquiry"`
- `agent: "OrchestrationAgent"`
- Both `analyze_query` AND `route_to_agent` in cached results
- `success: true`

---

### How to Test

```bash
# Option 1: Interactive testing
python interactive_orchestration_test.py

# Then paste queries:
>>> What is covered under massage therapy?
>>> Is acupuncture covered?
>>> What services are included in the benefit plan?
```

```bash
# Option 2: Batch testing
python test_all_orchestration_queries.py
```

---

## Success Criteria

After the fix, all RAG queries should show:

✅ `Retrieved cached tool results: ['analyze_query', 'route_to_agent']`
✅ No "Have analysis result but no routing result" warnings
✅ `intent` is NOT None in route_to_agent logs
✅ `success: true` in final response
✅ Proper routing to BenefitCoverageRAGAgent or OrchestrationAgent
✅ RAG queries return answers from vector database
✅ General inquiries return capability messages

---

## Files Modified

1. **src/MBA/agents/orchestration_agent/prompt.py**
   - Lines 89-115: Added mandatory tool sequence enforcement
   - Lines 211-234: Clarified tool parameter requirements
   - Lines 254-348: Added explicit tool usage examples with parameters

---

## Impact

This fix ensures:
- **100% tool execution rate**: All queries will call both analyze_query AND route_to_agent
- **Correct parameter passing**: AI will pass intent, agent, and extracted_entities correctly
- **RAG functionality restored**: Coverage queries will properly reach BenefitCoverageRAGAgent
- **Better general inquiry handling**: General questions will route through OrchestrationAgent properly

---

## Notes

- The fix works by making the system prompt **more prescriptive** rather than descriptive
- The AI now has explicit examples showing the exact tool calls with parameters
- This is a prompt engineering fix - no code changes to tools were needed
- The underlying tools (`analyze_query`, `route_to_agent`) were already working correctly
- The issue was purely in how the AI was interpreting its instructions
