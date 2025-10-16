# AWS Bedrock Configuration Guide for MBA System

Complete step-by-step guide to configure AWS Bedrock models (Claude, Titan Embeddings, and Cohere Rerank) for the MBA (Medical Benefits Administration) system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Part 1: Enable Bedrock Model Access](#part-1-enable-bedrock-model-access)
3. [Part 2: Configure IAM Permissions](#part-2-configure-iam-permissions)
4. [Part 3: Verify Configuration](#part-3-verify-configuration)
5. [Part 4: Update Environment Variables](#part-4-update-environment-variables)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- AWS Account with admin access
- AWS region that supports all Bedrock models:
  - **Recommended regions:**
    - `us-east-1` (N. Virginia) - ✅ All models available
    - `us-west-2` (Oregon) - ✅ All models available
  - **Supported regions:**
    - `eu-west-1` (Ireland)
    - `ap-southeast-1` (Singapore)

---

## Part 1: Enable Bedrock Model Access

### Step 1.1: Navigate to AWS Bedrock Console

1. **Open AWS Console:** https://console.aws.amazon.com/bedrock/home
2. **Select your region** (top-right dropdown)
   - Choose `us-east-1` or `us-west-2` for best model availability
3. **Wait for Bedrock console to load** (may take 10-15 seconds on first visit)

### Step 1.2: Access Model Access Page

1. **In the left sidebar**, click **"Model access"**
   - Or navigate to: `Amazon Bedrock > Foundation models > Model access`
2. You'll see a list of all available foundation models

### Step 1.3: Request Model Access

1. Click the **"Manage model access"** button (top-right)
2. You'll see a list of model providers with checkboxes

#### Enable Claude Models (Anthropic)

Scroll to **"Anthropic"** section and check:

- ☑️ **Claude 3.5 Sonnet v2** (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
- ☑️ **Claude 3.5 Sonnet** (`anthropic.claude-3-5-sonnet-20240620-v1:0`)
- ☑️ **Claude 3 Opus** (optional, for future use)
- ☑️ **Claude 3 Haiku** (optional, for cost-effective queries)

#### Enable Titan Embeddings (Amazon)

Scroll to **"Amazon"** section and check:

- ☑️ **Titan Embeddings G1 - Text v2** (`amazon.titan-embed-text-v2:0`)
- ☑️ **Titan Text G1 - Premier** (optional)

#### Enable Cohere Rerank

Scroll to **"Cohere"** section and check:

- ☑️ **Cohere Rerank v3.5** (`cohere.rerank-v3-5:0`) - **Latest & Recommended**
- ☑️ **Cohere Rerank v2.5** (`cohere.rerank-v2-5:0`) - Optional fallback

### Step 1.4: Submit Request

1. **Review your selections:**
   - Total: 3 providers (Anthropic, Amazon, Cohere)
   - Total: 5-8 models
2. **Read and accept the End User License Agreements (EULAs)**
   - Check the box: ☑️ "I have reviewed and agree to the EULAs"
3. Click **"Request model access"** or **"Save changes"**

### Step 1.5: Wait for Approval

1. **Status will change:**
   - "Requesting..." (yellow icon)
   - "Access granted" (green checkmark) ✅
2. **Wait time:** Usually 1-2 minutes (instant for most AWS accounts)
3. **Refresh the page** if status doesn't update

### Step 1.6: Verify Access

Return to **Model access** page and confirm:

| Model | Status | Model ID |
|-------|--------|----------|
| Claude 3.5 Sonnet v2 | ✅ Access granted | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Titan Embeddings v2 | ✅ Access granted | `amazon.titan-embed-text-v2:0` |
| Cohere Rerank v3.5 | ✅ Access granted | `cohere.rerank-v3-5:0` |

---

## Part 2: Configure IAM Permissions

You need to configure IAM permissions for:
1. **IAM Role** (for Lambda functions, EC2, ECS)
2. **IAM User** (for local development)

### Option A: Configure IAM Role (For Production - Lambda/EC2/ECS)

#### Step A1: Navigate to IAM Roles

1. Open **IAM Console:** https://console.aws.amazon.com/iam/home
2. Click **"Roles"** in the left sidebar
3. **Search for your role:**
   - Lambda role: Search for "lambda" (e.g., `MBA-Lambda-Role`)
   - EC2 role: Search for "ec2" (e.g., `MBA-EC2-Role`)
   - ECS role: Search for "ecs" (e.g., `MBA-ECS-TaskRole`)

#### Step A2: Create Bedrock Policy

1. Click **"Policies"** in the left sidebar
2. Click **"Create policy"**
3. Switch to the **JSON** tab
4. **Paste this complete policy:**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockClaudeAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-opus-20240229-v1:0",
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
            ]
        },
        {
            "Sid": "BedrockTitanEmbeddingsAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1"
            ]
        },
        {
            "Sid": "BedrockCohereRerankAccess",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/cohere.rerank-v3-5:0",
                "arn:aws:bedrock:*::foundation-model/cohere.rerank-v2-5:0"
            ]
        },
        {
            "Sid": "BedrockModelDiscovery",
            "Effect": "Allow",
            "Action": [
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel",
                "bedrock:ListModelCustomizationJobs",
                "bedrock:GetModelInvocationLoggingConfiguration"
            ],
            "Resource": "*"
        }
    ]
}
```

5. Click **"Next: Tags"** (skip tags)
6. Click **"Next: Review"**
7. **Enter policy details:**
   - **Policy name:** `MBA-Bedrock-FullAccess-Policy`
   - **Description:** `Allows MBA system to invoke all required AWS Bedrock models (Claude, Titan, Cohere Rerank)`
8. Click **"Create policy"**

#### Step A3: Attach Policy to Role

1. Return to **Roles** page
2. **Find and click your role** (e.g., `MBA-Lambda-Role`)
3. Click **"Add permissions"** dropdown
4. Select **"Attach policies"**
5. **Search for:** `MBA-Bedrock-FullAccess-Policy`
6. **Check the box** next to your policy
7. Click **"Attach policies"**

#### Step A4: Verify Role Permissions

1. Click on your role
2. Go to **"Permissions"** tab
3. **Confirm you see:**
   - `MBA-Bedrock-FullAccess-Policy` ✅
   - Other existing policies (S3, RDS, Textract, etc.)

---

### Option B: Configure IAM User (For Development)

#### Step B1: Navigate to IAM Users

1. Open **IAM Console:** https://console.aws.amazon.com/iam/home
2. Click **"Users"** in the left sidebar
3. **Search for your user:**
   - Development user: e.g., `mba-developer`, `john.doe`, or your AWS username

#### Step B2: Attach Bedrock Policy to User

1. **Click on your username**
2. Go to **"Permissions"** tab
3. Click **"Add permissions"** dropdown
4. Select **"Attach policies directly"**
5. **Search for:** `MBA-Bedrock-FullAccess-Policy` (created in Step A2)
6. **Check the box** next to the policy
7. Click **"Add permissions"**

#### Step B3: Verify User Permissions

1. Go to **"Permissions"** tab
2. **Confirm you see:**
   - `MBA-Bedrock-FullAccess-Policy` ✅
   - Other development policies (S3, RDS, etc.)

---

### Complete IAM Policy (All MBA Services)

For a **complete production-ready IAM policy** including Bedrock, S3, RDS, and Textract:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockLLMAccess",
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
            "Sid": "BedrockModelList",
            "Effect": "Allow",
            "Action": [
                "bedrock:ListFoundationModels",
                "bedrock:GetFoundationModel"
            ],
            "Resource": "*"
        },
        {
            "Sid": "S3DocumentAccess",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::YOUR-MBA-BUCKET-NAME",
                "arn:aws:s3:::YOUR-MBA-BUCKET-NAME/*"
            ]
        },
        {
            "Sid": "TextractDocumentProcessing",
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
            "Sid": "RDSDatabaseAccess",
            "Effect": "Allow",
            "Action": [
                "rds:DescribeDBInstances",
                "rds-db:connect"
            ],
            "Resource": [
                "arn:aws:rds:*:*:db:YOUR-MBA-DB-NAME"
            ]
        },
        {
            "Sid": "CloudWatchLogsAccess",
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

**Important:** Replace these placeholders:
- `YOUR-MBA-BUCKET-NAME` → Your actual S3 bucket name (e.g., `mb-assistant-bucket`)
- `YOUR-MBA-DB-NAME` → Your RDS database identifier (e.g., `mba-production-db`)

---

## Part 3: Verify Configuration

### Step 3.1: Test with AWS CLI (Optional but Recommended)

**Test Claude Model:**
```bash
aws bedrock-runtime invoke-model \
    --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
    --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}' \
    --region us-east-1 \
    output.json

cat output.json
```

**Expected Output:**
```json
{
  "content": [
    {
      "text": "Hello! How can I assist you today?",
      "type": "text"
    }
  ],
  "id": "msg_xxx",
  "model": "claude-3-5-sonnet-20241022",
  ...
}
```

**Test Titan Embeddings:**
```bash
aws bedrock-runtime invoke-model \
    --model-id amazon.titan-embed-text-v2:0 \
    --body '{"inputText":"Test embedding"}' \
    --region us-east-1 \
    embedding_output.json

cat embedding_output.json
```

**Expected Output:**
```json
{
  "embedding": [0.123, -0.456, 0.789, ...],  // 1536 dimensions
  "inputTextTokenCount": 2
}
```

**Test Cohere Rerank:**
```bash
aws bedrock-runtime invoke-model \
    --model-id cohere.rerank-v3-5:0 \
    --body '{"query":"What is massage therapy?","documents":["Doc 1: Massage therapy is covered.","Doc 2: Physical therapy info."],"top_n":2}' \
    --region us-east-1 \
    rerank_output.json

cat rerank_output.json
```

**Expected Output:**
```json
{
  "id": "xxx",
  "results": [
    {
      "index": 0,
      "relevance_score": 0.95
    },
    {
      "index": 1,
      "relevance_score": 0.23
    }
  ]
}
```

### Step 3.2: Test from Your MBA Application

Run this Python test script:

```python
# test_bedrock_access.py
import boto3
import json
import os

# Set your region
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

def test_claude():
    """Test Claude model access."""
    print("Testing Claude 3.5 Sonnet v2...")
    try:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {"role": "user", "content": "Say 'Bedrock is working!'"}
            ]
        }

        response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        print(f"✅ Claude Response: {result['content'][0]['text']}")
        return True
    except Exception as e:
        print(f"❌ Claude Error: {e}")
        return False

def test_titan_embeddings():
    """Test Titan Embeddings access."""
    print("\nTesting Titan Embeddings v2...")
    try:
        payload = {"inputText": "Test embedding"}

        response = bedrock_runtime.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        embedding = result['embedding']
        print(f"✅ Titan Embeddings: Generated {len(embedding)}-dimensional vector")
        return True
    except Exception as e:
        print(f"❌ Titan Error: {e}")
        return False

def test_cohere_rerank():
    """Test Cohere Rerank access."""
    print("\nTesting Cohere Rerank v3.5...")
    try:
        payload = {
            "query": "What is massage therapy?",
            "documents": [
                "Massage therapy is a covered benefit.",
                "Physical therapy requires authorization."
            ],
            "top_n": 2
        }

        response = bedrock_runtime.invoke_model(
            modelId="cohere.rerank-v3-5:0",
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        print(f"✅ Cohere Rerank: Reranked {len(result['results'])} documents")
        for i, item in enumerate(result['results']):
            print(f"   Document {item['index']}: Relevance = {item['relevance_score']:.2f}")
        return True
    except Exception as e:
        print(f"❌ Cohere Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("AWS BEDROCK ACCESS TEST")
    print("=" * 60)

    results = []
    results.append(("Claude 3.5 Sonnet", test_claude()))
    results.append(("Titan Embeddings", test_titan_embeddings()))
    results.append(("Cohere Rerank", test_cohere_rerank()))

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n🎉 All Bedrock models configured correctly!")
    else:
        print("\n⚠️  Some models failed. Check IAM permissions and model access.")
```

**Run the test:**
```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT
python test_bedrock_access.py
```

**Expected Output:**
```
============================================================
AWS BEDROCK ACCESS TEST
============================================================
Testing Claude 3.5 Sonnet v2...
✅ Claude Response: Bedrock is working!

Testing Titan Embeddings v2...
✅ Titan Embeddings: Generated 1536-dimensional vector

Testing Cohere Rerank v3.5...
✅ Cohere Rerank: Reranked 2 documents
   Document 0: Relevance = 0.95
   Document 1: Relevance = 0.23

============================================================
TEST SUMMARY
============================================================
✅ PASS: Claude 3.5 Sonnet
✅ PASS: Titan Embeddings
✅ PASS: Cohere Rerank

🎉 All Bedrock models configured correctly!
```

---

## Part 4: Update Environment Variables

### Step 4.1: Update `.env` File

Edit your `.env` file to include Bedrock configuration:

```bash
# AWS Configuration
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=your-aws-profile  # For local development
# AWS_ACCESS_KEY_ID=your-key-id  # Alternative to profile
# AWS_SECRET_ACCESS_KEY=your-secret-key

# AWS Bedrock Model IDs
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0

# Bedrock Configuration
BEDROCK_MAX_TOKENS=4000
BEDROCK_TEMPERATURE=0.3
EMBEDDING_DIMENSION=1536

# Vector Store Configuration
OPENSEARCH_INDEX=benefit_coverage_rag_index
VECTOR_FIELD=vector_field

# S3 Configuration
S3_BUCKET_NAME=your-mba-bucket-name

# Database Configuration
DB_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_NAME=mba_db
DB_USER=admin
DB_PASSWORD=your-secure-password
```

### Step 4.2: Update Lambda Environment Variables

If deploying to Lambda:

1. **Open Lambda Console:** https://console.aws.amazon.com/lambda/home
2. **Click on your Lambda function**
3. Go to **Configuration** tab → **Environment variables**
4. Click **Edit**
5. **Add these variables:**

| Key | Value |
|-----|-------|
| `AWS_DEFAULT_REGION` | `us-east-1` |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `BEDROCK_EMBEDDING_MODEL_ID` | `amazon.titan-embed-text-v2:0` |
| `BEDROCK_RERANK_MODEL_ID` | `cohere.rerank-v3-5:0` |
| `EMBEDDING_DIMENSION` | `1536` |
| `OPENSEARCH_INDEX` | `benefit_coverage_rag_index` |

6. Click **Save**

---

## Troubleshooting

### Issue 1: "AccessDeniedException" Error

**Error Message:**
```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling the InvokeModel operation:
User: arn:aws:iam::123456789:user/xxx is not authorized to perform: bedrock:InvokeModel
```

**Solution:**
1. Verify IAM policy is attached to your role/user
2. Check policy has `bedrock:InvokeModel` permission
3. Verify model ARN in policy matches the region you're using
4. Wait 1-2 minutes for IAM changes to propagate

### Issue 2: "Model Not Found" Error

**Error Message:**
```
ResourceNotFoundException: Could not find foundation model with modelId cohere.rerank-v3-5:0
```

**Solution:**
1. Check you're in the correct region (use `us-east-1` or `us-west-2`)
2. Verify model access is granted in Bedrock console
3. Check the model ID is correct (no typos)

### Issue 3: "ValidationException" for Rerank

**Error Message:**
```
ValidationException: Validation error: documents must be a list
```

**Solution:**
1. Ensure `documents` parameter is a list of strings
2. Check `query` is a string (not a dict)
3. Verify JSON payload format:
   ```python
   payload = {
       "query": "your question",
       "documents": ["doc1", "doc2"],
       "top_n": 5
   }
   ```

### Issue 4: Rate Limiting

**Error Message:**
```
ThrottlingException: Rate exceeded
```

**Solution:**
1. Implement exponential backoff retry logic
2. Request quota increase in AWS Service Quotas console
3. Current limits:
   - Claude: 10 requests/second per region
   - Titan Embeddings: 50 requests/second
   - Cohere Rerank: 10 requests/second

### Issue 5: Large Payload for Rerank

**Error Message:**
```
ValidationException: Input payload size exceeds maximum allowed
```

**Solution:**
1. Limit documents to top 50-100 before reranking
2. Truncate document text to 2000 characters each
3. Cohere Rerank limits:
   - Max documents: 1000
   - Max total payload: 1 MB

---

## Next Steps

### 1. Test RAG Pipeline End-to-End

```bash
# 1. Upload a PDF
curl -X POST http://localhost:8000/upload/ \
  -F "file=@benefits_policy.pdf"

# 2. Prepare RAG pipeline
curl -X POST http://localhost:8000/benefit-coverage-rag/prepare \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "your-bucket",
    "textract_prefix": "mba/textract-output/..."
  }'

# 3. Query RAG
curl -X POST http://localhost:8000/benefit-coverage-rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Is massage therapy covered?"
  }'
```

### 2. Monitor Bedrock Usage

1. **Open CloudWatch Console:** https://console.aws.amazon.com/cloudwatch/home
2. Go to **Logs** → **Log groups**
3. Find your Lambda log group: `/aws/lambda/your-function-name`
4. **Monitor Bedrock API calls and costs**

### 3. Set Up Cost Alerts

1. **Open AWS Cost Explorer**
2. Create a budget alert for Bedrock costs
3. **Recommended monthly budget:**
   - Development: $50-100
   - Production: $200-500 (depends on query volume)

---

## Cost Estimation

| Model | Cost per 1K Tokens | Example Usage | Monthly Cost |
|-------|-------------------|---------------|--------------|
| Claude 3.5 Sonnet v2 | Input: $0.003<br>Output: $0.015 | 10K queries/month<br>500 tokens/query | ~$40 |
| Titan Embeddings v2 | $0.00002 per token | 50K documents<br>200 tokens/doc | ~$0.20 |
| Cohere Rerank v3.5 | $0.002 per 1K search units | 10K queries<br>10 docs/query | ~$2 |
| **Total** | | | **~$42/month** |

---

## Security Best Practices

1. **Never commit AWS credentials to Git**
   - Use `.env` for local development
   - Use IAM roles for Lambda/EC2
   - Use AWS Secrets Manager for production secrets

2. **Use least privilege IAM policies**
   - Only grant access to models you need
   - Restrict by region if possible
   - Use resource-level permissions

3. **Enable CloudTrail logging**
   - Track all Bedrock API calls
   - Set up alerts for unusual activity

4. **Rotate credentials regularly**
   - Rotate IAM access keys every 90 days
   - Use temporary credentials when possible

---

## Summary Checklist

- [ ] AWS Bedrock Model Access granted for:
  - [ ] Claude 3.5 Sonnet v2
  - [ ] Titan Embeddings v2
  - [ ] Cohere Rerank v3.5
- [ ] IAM Policy created: `MBA-Bedrock-FullAccess-Policy`
- [ ] IAM Role updated (for Lambda/EC2)
- [ ] IAM User updated (for development)
- [ ] Environment variables configured
- [ ] Bedrock access tested with Python script
- [ ] RAG pipeline tested end-to-end
- [ ] Cost alerts configured
- [ ] CloudWatch logging enabled

---

## Additional Resources

- **AWS Bedrock Documentation:** https://docs.aws.amazon.com/bedrock/
- **Claude API Reference:** https://docs.anthropic.com/claude/reference/
- **Cohere Rerank API:** https://docs.cohere.com/reference/rerank
- **Boto3 Bedrock Runtime:** https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime.html

---

**Configuration Date:** October 2025
**MBA System Version:** 1.0
**Maintained by:** MBA Development Team
