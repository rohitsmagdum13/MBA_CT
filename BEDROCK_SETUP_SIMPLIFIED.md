# AWS Bedrock Setup - Simplified Guide (Updated Oct 2025)

**Quick setup guide for AWS Bedrock Cohere Rerank + Claude + Titan Embeddings for MBA System**

---

## ✅ Good News: Model Access is Automatic!

AWS Bedrock has simplified model access. **All serverless foundation models are now automatically enabled** for your AWS account.

**What this means:**
- ❌ **No need to manually request model access**
- ❌ **No "Model Access" page to navigate**
- ❌ **No waiting for approval**
- ✅ **Just configure IAM permissions and start using models!**

---

## Setup Steps (Total: 10 minutes)

### Step 1: Configure IAM Permissions (8 minutes)

This is the **only** required configuration step now.

#### Option A: For Lambda/EC2/ECS (Production)

1. **Open IAM Console:** https://console.aws.amazon.com/iam/home
2. Click **"Policies"** → **"Create policy"**
3. Switch to **JSON** tab
4. **Paste this policy:**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockAllModelsAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
                "arn:aws:bedrock:*::foundation-model/cohere.rerank-v3-5:0",
                "arn:aws:bedrock:*::foundation-model/cohere.rerank-v2-5:0"
            ]
        },
        {
            "Sid": "BedrockModelDiscovery",
            "Effect": "Allow",
            "Action": [
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel"
            ],
            "Resource": "*"
        }
    ]
}
```

5. Click **"Next"**
6. **Policy name:** `MBA-Bedrock-FullAccess-Policy`
7. **Description:** `Allows MBA system to use Claude, Titan Embeddings, and Cohere Rerank`
8. Click **"Create policy"**

#### Attach Policy to Your Role/User

**For Lambda Role:**
1. Go to **"Roles"** → Find your Lambda role (e.g., `MBA-Lambda-Role`)
2. Click **"Add permissions"** → **"Attach policies"**
3. Search for `MBA-Bedrock-FullAccess-Policy`
4. Check the box → Click **"Attach policies"**

**For IAM User (Development):**
1. Go to **"Users"** → Find your user
2. Click **"Add permissions"** → **"Attach policies directly"**
3. Search for `MBA-Bedrock-FullAccess-Policy`
4. Check the box → Click **"Add permissions"**

---

### Step 2: Update Environment Variables (1 minute)

Add to your `.env` file:

```bash
# AWS Configuration
AWS_DEFAULT_REGION=us-east-1

# Bedrock Model IDs
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0

# Bedrock Configuration
EMBEDDING_DIMENSION=1536
OPENSEARCH_INDEX=benefit_coverage_rag_index
```

---

### Step 3: Test Configuration (1 minute)

Run the test script:

```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT
python test_bedrock_access.py
```

**Expected output:**

```
============================================================
AWS BEDROCK ACCESS TEST FOR MBA SYSTEM
============================================================

TEST 1: Claude 3.5 Sonnet v2 (LLM)
✅ Response received: AWS Bedrock Claude is working correctly!

TEST 2: Titan Embeddings v2 (Embeddings)
✅ Embedding generated successfully: Dimension: 1536

TEST 3: Cohere Rerank v3.5 (Document Reranking)
✅ Reranking completed successfully: Reranked 5 documents

============================================================
TEST SUMMARY
============================================================
✅ PASS: Claude 3.5 Sonnet v2
✅ PASS: Titan Embeddings v2
✅ PASS: Cohere Rerank v3.5

🎉 SUCCESS: All Bedrock models configured correctly!
```

---

## Optional: Verify Models in Console

If you want to see available models in the console:

1. Go to: https://console.aws.amazon.com/bedrock/home
2. Select region: `us-east-1`
3. Click **"Model catalog"** in left sidebar
4. Search for:
   - "Claude 3.5 Sonnet" → See Claude models
   - "Titan Embeddings" → See `titan-embed-text-v2:0`
   - "Cohere Rerank" → See `rerank-v3-5:0`

5. **Optional:** Click "View in playground" to test models interactively

**Note:** Some first-time users may be asked to submit use case details for Anthropic Claude models. This is a one-time form that takes 2-3 minutes.

---

## Complete IAM Policy (All MBA Services)

If you want a **single policy** for all MBA services (Bedrock + S3 + RDS + Textract):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.*",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-*",
                "arn:aws:bedrock:*::foundation-model/cohere.*",
                "*"
            ]
        },
        {
            "Sid": "S3Access",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::YOUR-BUCKET-NAME",
                "arn:aws:s3:::YOUR-BUCKET-NAME/*"
            ]
        },
        {
            "Sid": "TextractAccess",
            "Effect": "Allow",
            "Action": [
                "textract:DetectDocumentText",
                "textract:AnalyzeDocument",
                "textract:GetDocumentAnalysis",
                "textract:StartDocumentAnalysis"
            ],
            "Resource": "*"
        },
        {
            "Sid": "RDSAccess",
            "Effect": "Allow",
            "Action": [
                "rds:DescribeDBInstances",
                "rds-db:connect"
            ],
            "Resource": "arn:aws:rds:*:*:db:YOUR-DB-NAME"
        },
        {
            "Sid": "CloudWatchLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

**Replace:**
- `YOUR-BUCKET-NAME` → Your S3 bucket (e.g., `mb-assistant-bucket`)
- `YOUR-DB-NAME` → Your RDS database (e.g., `mba-production-db`)

---

## Troubleshooting

### Error: AccessDeniedException

**Problem:** IAM policy not attached or incorrect

**Solution:**
1. Verify policy is attached to your role/user in IAM console
2. Check policy has `bedrock:InvokeModel` permission
3. Wait 1-2 minutes for IAM changes to propagate
4. Try again

### Error: ResourceNotFoundException (Model not found)

**Problem:** Wrong region or model ID typo

**Solution:**
1. Use `us-east-1` or `us-west-2` region
2. Verify model IDs:
   - Claude: `anthropic.claude-3-5-sonnet-20241022-v2:0`
   - Titan: `amazon.titan-embed-text-v2:0`
   - Cohere: `cohere.rerank-v3-5:0`

### Error: ValidationException (Cohere Rerank)

**Problem:** Incorrect payload format

**Solution:**
Ensure payload format is correct:
```python
payload = {
    "query": "search query here",
    "documents": ["doc1", "doc2", "doc3"],  # List of strings
    "top_n": 5
}
```

---

## Code Integration - Already Done! ✅

Your code already has Cohere Rerank integrated:

**File:** [src/MBA/agents/benefit_coverage_rag_agent/tools.py:149-179](src/MBA/agents/benefit_coverage_rag_agent/tools.py#L149-L179)

```python
def rerank_documents(query: str, documents: List[str], top_n: int = 5) -> List[int]:
    """Rerank documents using AWS Bedrock Cohere Rerank."""
    payload = {
        "query": query,
        "documents": documents,
        "top_n": min(top_n, len(documents))
    }

    response = bedrock_runtime.invoke_model(
        modelId="cohere.rerank-v3-5:0",  # ✅ Already configured
        body=json.dumps(payload)
    )

    result = json.loads(response['body'].read())
    return [item["index"] for item in result.get("results", [])]
```

**Used in:** [tools.py:575](src/MBA/agents/benefit_coverage_rag_agent/tools.py#L575) during RAG queries

**No code changes needed!** Just set up IAM permissions and it will work.

---

## Cost Estimation

| Model | Usage | Cost |
|-------|-------|------|
| Claude 3.5 Sonnet | 10K queries/month | ~$40/month |
| Titan Embeddings | 50K documents | ~$0.20/month |
| **Cohere Rerank** | **10K queries** | **~$2/month** |
| **Total** | | **~$42/month** |

**Cohere Rerank is very affordable** at ~$0.002 per 1K search units (10 documents = 1 search unit).

---

## Summary Checklist

- [ ] IAM Policy created: `MBA-Bedrock-FullAccess-Policy`
- [ ] Policy attached to Lambda role **OR** IAM user
- [ ] Environment variables added to `.env`
- [ ] Test script passed all 3 tests
- [ ] Ready to use RAG pipeline!

---

## Quick Reference

| What | Value |
|------|-------|
| **Region** | `us-east-1` or `us-west-2` |
| **Claude Model ID** | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| **Titan Embeddings ID** | `amazon.titan-embed-text-v2:0` |
| **Cohere Rerank ID** | `cohere.rerank-v3-5:0` |
| **IAM Permission** | `bedrock:InvokeModel` |
| **Test Script** | `python test_bedrock_access.py` |

---

## Additional Resources

- **AWS Bedrock Docs:** https://docs.aws.amazon.com/bedrock/
- **Model Catalog:** https://console.aws.amazon.com/bedrock/home → Model catalog
- **Cohere Rerank API:** https://docs.cohere.com/reference/rerank
- **EULAs:** https://aws.amazon.com/bedrock/eulas/

---

**Last Updated:** October 2025
**For:** MBA Medical Benefits Administration System
**Setup Time:** ~10 minutes
