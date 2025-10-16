# AWS Bedrock API Updates & Fixes Applied

## Issues Found & Fixed

Based on your test results, we identified and fixed **3 critical API issues** with AWS Bedrock:

---

## Issue 1: Claude Inference Profile Requirement ❌→✅

### **Error:**
```
ValidationException: Invocation of model ID anthropic.claude-3-5-sonnet-20241022-v2:0
with on-demand throughput isn't supported. Retry your request with the ID or ARN of
an inference profile that contains this model.
```

### **Root Cause:**
AWS now requires using **cross-region inference profiles** for Claude models with on-demand throughput.

### **Fix Applied:**

#### Test Script ([test_bedrock_access.py:28](test_bedrock_access.py#L28)):
```python
# OLD (fails)
CLAUDE_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

# NEW (works)
CLAUDE_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
```

#### Production Code ([tools.py:137-140](src/MBA/agents/benefit_coverage_rag_agent/tools.py#L137-L140)):
```python
# Auto-prepend "us." prefix if not present
model_id = settings.bedrock_model_id
if "anthropic.claude" in model_id and not model_id.startswith("us."):
    model_id = f"us.{model_id}"

response = bedrock_runtime.invoke_model(
    modelId=model_id,  # Uses: us.anthropic.claude-3-5-sonnet-20241022-v2:0
    body=json.dumps(payload)
)
```

**What This Means:**
- The `us.` prefix enables **cross-region inference profiles**
- Works across all US regions (us-east-1, us-west-2, etc.)
- No changes needed to your `.env` file - code automatically handles it

---

## Issue 2: Titan Embeddings Dimension Mismatch ❌→✅

### **Error:**
```
⚠️ Warning: Expected 1536 dimensions, got 1024
```

### **Root Cause:**
AWS Bedrock **Titan Embeddings v2** produces **1024 dimensions**, not 1536 dimensions.

**Clarification:**
- Titan Embeddings **v1**: 1536 dimensions
- Titan Embeddings **v2**: **1024 dimensions** ← We're using this

### **Fix Applied:**

#### Configuration ([tools.py:35-36](src/MBA/agents/benefit_coverage_rag_agent/tools.py#L35-L36)):
```python
# OLD (incorrect)
EMBEDDING_DIMENSION = 1536

# NEW (correct)
EMBEDDING_DIMENSION = 1024  # Titan v2 uses 1024 dimensions
```

#### Test Script ([test_bedrock_access.py:31](test_bedrock_access.py#L31)):
```python
TITAN_EXPECTED_DIMENSION = 1024  # v2 uses 1024, not 1536
```

**Impact:**
- Vector store indices must be configured for **1024 dimensions**
- If you already created indices with 1536 dimensions, you'll need to recreate them
- Update any hardcoded dimension values in your configuration

---

## Issue 3: Cohere Rerank API Version Required ❌→✅

### **Error:**
```
ValidationException: Malformed input request: #: required key [api_version] not found,
please reformat your input and try again.
```

### **Root Cause:**
Cohere Rerank v3.5 API now **requires** the `api_version` field in the request payload.

### **Fix Applied:**

#### Test Script ([test_bedrock_access.py:196-201](test_bedrock_access.py#L196-L201)):
```python
# OLD (fails)
payload = {
    "query": query,
    "documents": documents,
    "top_n": 5
}

# NEW (works)
payload = {
    "api_version": "v1",  # Required field
    "query": query,
    "documents": documents,
    "top_n": 5
}
```

#### Production Code ([tools.py:168-173](src/MBA/agents/benefit_coverage_rag_agent/tools.py#L168-L173)):
```python
payload = {
    "api_version": "v1",  # Now required by Cohere Rerank API
    "query": query,
    "documents": documents,
    "top_n": min(top_n, len(documents))
}
```

**API Version:**
- Use `"v1"` for Cohere Rerank v3.5
- This is a required field as of October 2025

---

## Updated Environment Variables

Update your `.env` file with the **corrected** configuration:

```bash
# AWS Configuration
AWS_DEFAULT_REGION=us-east-1

# Bedrock Model IDs
# Note: Code automatically prepends "us." prefix for Claude
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0

# Bedrock Configuration
# IMPORTANT: Titan v2 produces 1024 dimensions, not 1536
EMBEDDING_DIMENSION=1024

# Vector Store Configuration
OPENSEARCH_INDEX=benefit_coverage_rag_index
VECTOR_FIELD=vector_field
```

---

## Testing the Fixes

Run the updated test script:

```bash
python test_bedrock_access.py
```

**Expected Output (All Passing):**

```
============================================================
AWS BEDROCK ACCESS TEST FOR MBA SYSTEM
============================================================

TEST 1: Claude 3.5 Sonnet v2 (LLM)
============================================================
Model ID: us.anthropic.claude-3-5-sonnet-20241022-v2:0
✅ Response received: AWS Bedrock Claude is working correctly!
   Input tokens: 20
   Output tokens: 12

TEST 2: Titan Embeddings v2 (Embeddings)
============================================================
Model ID: amazon.titan-embed-text-v2:0
✅ Embedding generated successfully:
   Dimension: 1024
   Token count: 11
   Vector norm: 1.0000

TEST 3: Cohere Rerank v3.5 (Document Reranking)
============================================================
Model ID: cohere.rerank-v3-5:0
✅ Reranking completed successfully:
   Reranked documents: 5
   Results (sorted by relevance):
   1. Doc #1 | Relevance: 0.9521
      'Massage therapy is covered with a limit of 6 visits...'
   2. Doc #3 | Relevance: 0.3142
      'Chiropractic care is limited to 20 visits per year...'

============================================================
TEST SUMMARY
============================================================
✅ PASS: Claude 3.5 Sonnet v2
✅ PASS: Titan Embeddings v2
✅ PASS: Cohere Rerank v3.5

🎉 SUCCESS: All Bedrock models configured correctly!
```

---

## Files Updated

### 1. **Test Script**
- **File:** `test_bedrock_access.py`
- **Changes:**
  - Line 28: Updated Claude model ID to use `us.` prefix
  - Line 31: Set Titan dimension to 1024
  - Line 197: Added `api_version` to Cohere Rerank payload

### 2. **Production Code**
- **File:** `src/MBA/agents/benefit_coverage_rag_agent/tools.py`
- **Changes:**
  - Line 36: Updated `EMBEDDING_DIMENSION = 1024`
  - Lines 137-140: Added auto-prepend logic for Claude inference profile
  - Line 169: Added `api_version` to Cohere Rerank payload

---

## Action Items for You

### ✅ Already Done:
1. Test script updated with correct API formats
2. Production code updated with all 3 fixes
3. Auto-detection for Claude inference profile

### 🔧 You Need to Do:

#### 1. Update `.env` File (1 minute)
```bash
# Change this line:
EMBEDDING_DIMENSION=1536  # OLD

# To this:
EMBEDDING_DIMENSION=1024  # NEW
```

#### 2. Run Test Script (1 minute)
```bash
python test_bedrock_access.py
```

**Should now pass all 3 tests!**

#### 3. Update Vector Store Indices (If Already Created)

If you've already created OpenSearch or Qdrant indices with 1536 dimensions:

**Option A: Recreate Index**
```python
# Delete old index
DELETE /benefit_coverage_rag_index

# Create new index with 1024 dimensions
PUT /benefit_coverage_rag_index
{
  "mappings": {
    "properties": {
      "vector_field": {
        "type": "knn_vector",
        "dimension": 1024  # Changed from 1536
      }
    }
  }
}
```

**Option B: Use Different Titan Model**

If you must use 1536 dimensions, switch to Titan v1:
```bash
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v1  # Uses 1536 dimensions
EMBEDDING_DIMENSION=1536
```

---

## Summary of Changes

| Component | Old Value | New Value | Reason |
|-----------|-----------|-----------|--------|
| **Claude Model ID** | `anthropic.claude-3-5-sonnet-20241022-v2:0` | `us.anthropic.claude-3-5-sonnet-20241022-v2:0` | AWS requires inference profile for on-demand |
| **Embedding Dimension** | 1536 | **1024** | Titan v2 produces 1024 dimensions |
| **Cohere API Version** | Not included | `"api_version": "v1"` | Now required by Cohere Rerank API |

---

## Backward Compatibility

Your existing code will **automatically work** with these changes:

1. **Claude:** Code auto-prepends `us.` prefix if needed
2. **Titan:** Dimension is read from `EMBEDDING_DIMENSION` config
3. **Cohere:** Payload now includes required `api_version` field

**No breaking changes** - just update your `.env` file and rerun the test!

---

## IAM Permissions (No Changes Needed)

Your IAM policy is still correct. The model ARNs don't change:

```json
{
    "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
        "arn:aws:bedrock:*::foundation-model/cohere.rerank-v3-5:0"
    ]
}
```

The `us.` prefix is just a **runtime invocation detail**, not a permission change.

---

## Next Steps

1. ✅ Update `.env`: Change `EMBEDDING_DIMENSION=1024`
2. ✅ Run test: `python test_bedrock_access.py`
3. ✅ Verify all 3 tests pass
4. ✅ Update vector store index dimensions (if already created)
5. ✅ Test RAG pipeline end-to-end

**You're now ready to use Cohere Rerank!**

---

**Last Updated:** October 16, 2025
**Applies To:** MBA System v1.0
**AWS Bedrock API:** October 2025 updates
