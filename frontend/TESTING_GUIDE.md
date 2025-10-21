# Testing Guide - MBA Frontend with Orchestration

## ✅ Backend is Running Successfully!

Your backend logs show all agents are initialized:
- ✅ Member Verification Agent
- ✅ Deductible/OOP Agent
- ✅ Benefit Accumulator Agent
- ✅ Benefit Coverage RAG Agent
- ✅ Intent Identification Agent
- ✅ Orchestration Agent

---

## 🧪 Test Queries (Use These!)

### Test 1: Member Verification

**Query:**
```
Is member M1001 active?
```

**Expected:**
- Intent: `member_verification`
- Agent: `MemberVerificationAgent`
- Response shows member details

---

### Test 2: Deductible Query

**Query:**
```
What is the deductible for member M1234?
```

**Expected:**
- Intent: `deductible_oop`
- Agent: `DeductibleOOPAgent`
- Response shows deductible amounts

---

### Test 3: Benefit Accumulator

**Query:**
```
How many massage therapy visits has member M5678 used?
```

**Expected:**
- Intent: `benefit_accumulator`
- Agent: `BenefitAccumulatorAgent`
- Response shows visit usage

---

### Test 4: General Benefit Question

**Query:**
```
Tell me about member M1001
```

**Expected:**
- Intent: Auto-detected based on query
- Agent: Routes to appropriate agent
- Response: Member information

---

## 📋 Step-by-Step Testing

### 1. Start Backend (Already Running ✅)
Your backend is running at `http://127.0.0.1:8000`

### 2. Start Frontend
```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT\frontend
npm start
```

### 3. Open Browser
Navigate to: `http://localhost:3000`

### 4. Skip CSV Upload (Optional)
- CSV upload works, but you likely already have data in your database
- Go straight to Step 2: Ask Your Question

### 5. Test a Query
1. Enter one of the test queries above
2. Click "Get Answer"
3. Watch the AI:
   - Identify the intent
   - Route to the correct agent
   - Return the result
4. Check the response shows:
   - Intent chip (e.g., "Intent: member_verification")
   - Agent chip (e.g., "Agent: MemberVerificationAgent")
   - Confidence score
   - AI Reasoning
   - Formatted answer

---

## 🔍 What to Look For

### Success Indicators:
✅ Query processes without errors
✅ Intent is correctly identified
✅ Agent name is shown
✅ Confidence is > 80%
✅ Response has actual data (not just error message)

### Response Format Examples:

**Member Verification Response:**
```
Member Valid: Yes
Member ID: M1001
Name: John Doe
Date of Birth: 1990-01-01
```

**Deductible Response:**
```
Found: Yes
Individual Deductible: {...}
Family Deductible: {...}
```

**Benefit Accumulator Response:**
```
Found: Yes
Benefits:
  - Massage Therapy: 6 allowed, 3 used, 3 remaining
```

---

## 🚨 Common Issues & Solutions

### Issue: "Member ID not found"
**Solution:** Use a member ID that exists in your database
- Check your database: `SELECT member_id FROM memberdata LIMIT 10;`
- Use one of those IDs in your query

### Issue: "Service not initialized"
**Solution:** Restart backend
```bash
# Stop backend (Ctrl+C)
# Restart:
uvicorn MBA.microservices.api:app --reload
```

### Issue: "No response from orchestrator"
**Solution:** Check backend is running
```bash
# Test backend health:
curl http://127.0.0.1:8000/health
```

### Issue: CORS error in browser console
**Solution:** Backend already configured for `localhost:3000`
- If using different port, update backend CORS settings

---

## 🎯 Testing Workflow

```
User Query
    ↓
Intent Identification Agent
    ↓
(Identifies intent with confidence)
    ↓
Orchestration Agent
    ↓
Routes to Specialized Agent:
    ├─→ Member Verification Agent
    ├─→ Deductible/OOP Agent
    ├─→ Benefit Accumulator Agent
    └─→ Benefit Coverage RAG Agent
    ↓
Agent Executes Query
    ↓
Returns Structured Response
    ↓
Frontend Formats & Displays
```

---

## 📊 Expected API Call Flow

### 1. User enters query → Frontend sends:
```http
POST http://127.0.0.1:8000/orchestrate/query
{
  "query": "Is member M1001 active?",
  "context": {},
  "preserve_history": false
}
```

### 2. Backend processes:
```
Orchestration Agent receives query
    ↓
Intent Identification Agent analyzes
    ↓
Intent: "member_verification" (confidence: 0.95)
    ↓
Routes to Member Verification Agent
    ↓
Queries database
    ↓
Returns result
```

### 3. Backend responds:
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
    "dob": "1990-01-01"
  },
  "reasoning": "Detected member ID: M1001",
  "extracted_entities": {
    "member_id": "M1001"
  }
}
```

### 4. Frontend displays:
- Intent chip: "Intent: member_verification"
- Agent chip: "Agent: MemberVerificationAgent"
- Confidence: "Confidence: 95%"
- Reasoning alert
- Formatted answer with member details

---

## 🎓 Understanding the Response

### Intent Types:
1. **member_verification** - Verify member identity/status
2. **deductible_oop** - Query deductibles and out-of-pocket maximums
3. **benefit_accumulator** - Check benefit usage/limits
4. **benefit_coverage_rag** - Answer policy coverage questions
5. **general_inquiry** - Fallback for unclassified queries

### Confidence Levels:
- **90-100%**: Very confident - exact pattern match
- **70-89%**: Confident - strong indicators
- **50-69%**: Moderate - some uncertainty
- **<50%**: Low confidence - may route to general_inquiry

---

## ✅ Successful Test Checklist

- [ ] Frontend loads at `http://localhost:3000`
- [ ] Backend health check returns healthy status
- [ ] Test query #1 (Member Verification) works
- [ ] Test query #2 (Deductible) works
- [ ] Test query #3 (Benefit Accumulator) works
- [ ] Response shows correct intent
- [ ] Response shows correct agent
- [ ] Confidence score is displayed
- [ ] Answer is formatted correctly
- [ ] Execution time is shown

---

## 🐛 Debugging

### Check Backend Logs:
Your backend terminal shows detailed logs for each request. Look for:
```
INFO | Orchestration Agent receives query
INFO | Intent identified: member_verification
INFO | Routing to MemberVerificationAgent
INFO | Query executed successfully
```

### Check Browser Console:
Open browser DevTools (F12) → Console tab
Look for:
- Network errors
- CORS errors
- JavaScript errors

### Check Network Tab:
DevTools → Network tab → Click on API request
- Check request payload
- Check response status (should be 200)
- Check response body

---

## 🎉 Success Criteria

Your system is working when:
1. You can enter a natural language query
2. The AI correctly identifies the intent
3. The query is routed to the right agent
4. You get a formatted response with actual data
5. The whole process takes < 3 seconds

---

**Ready to test? Start with: "Is member M1001 active?"** 🚀
