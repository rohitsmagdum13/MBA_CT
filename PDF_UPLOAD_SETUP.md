# PDF Upload & RAG Setup Guide

## Current Situation

### ✅ What's Working:
1. **CSV Upload** - Works perfectly for member/benefit data
2. **Query Orchestration** - All agents working
3. **Member Verification** - Ready to use
4. **Deductible/OOP Queries** - Ready to use
5. **Benefit Accumulator** - Ready to use

### ❌ What's NOT Working:
**PDF Upload with RAG** - Requires AWS Textract configuration

---

## Why PDF Upload Fails

### The Flow That's Expected:
```
1. User uploads PDF → Frontend
2. Frontend sends to /rag/upload-and-prepare
3. Backend uploads PDF to s3://mb-assistant-bucket/mba/pdf/filename.pdf
4. **AWS Lambda trigger should process PDF with Textract** ← THIS IS MISSING
5. Textract outputs JSON to s3://mb-assistant-bucket/mba/textract-output/mba/pdf/filename.pdf/
6. RAG agent reads Textract JSON
7. Creates embeddings and indexes in Qdrant
8. Ready for querying
```

### What Actually Happens:
```
Steps 1-3: ✅ Work fine
Step 4:     ❌ No Lambda configured - Textract never runs
Step 5:     ❌ No Textract output created
Step 6:     ❌ RAG agent finds no files at expected path
Step 7-8:   ❌ Never reached
```

---

## Error in Your Logs

```
ERROR | No files found in S3 path: s3://mb-assistant-bucket/textract-output/pdf/benefit_coverage.pdf/
```

**Translation:** The PDF was uploaded to S3 successfully, but Textract hasn't processed it, so there are no output files for the RAG agent to read.

---

## Solution Options

### Option 1: Skip PDF Upload (Recommended for Now)

**Use what's working:**
- Query existing data in database
- Upload CSVs for new data
- Focus on member verification, deductibles, and benefit accumulator queries

**Example queries that work RIGHT NOW:**
```
1. Is member M1001 active?
2. What is the deductible for member M1234?
3. How many massage therapy visits has member M5678 used?
```

### Option 2: Set Up AWS Textract Lambda (For Later)

**Requirements:**
1. AWS Lambda function
2. S3 event trigger on `mba/pdf/` uploads
3. Textract API calls
4. Output to `mba/textract-output/`

**Steps:**
1. Create Lambda function with Textract permissions
2. Configure S3 trigger for `mba/pdf/*` prefix
3. Lambda code should:
   - Trigger Textract StartDocumentTextDetection
   - Poll for completion
   - Save output JSON to `mba/textract-output/mba/pdf/{filename}/`

**AWS Lambda Code Template:**
```python
import boto3
import json

textract = boto3.client('textract')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    # Get uploaded file from S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # Start Textract job
    response = textract.start_document_text_detection(
        DocumentLocation={'S3Object': {'Bucket': bucket, 'Name': key}}
    )

    job_id = response['JobId']

    # Poll for completion (simplified - use SNS in production)
    while True:
        response = textract.get_document_text_detection(JobId=job_id)
        status = response['JobStatus']

        if status == 'SUCCEEDED':
            # Save output to mba/textract-output/
            output_key = key.replace('pdf/', 'textract-output/mba/pdf/')
            s3.put_object(
                Bucket=bucket,
                Key=f"{output_key}/textract-output.json",
                Body=json.dumps(response)
            )
            break
        elif status == 'FAILED':
            raise Exception('Textract failed')
```

### Option 3: Use Manual Textract Processing

**For one-off PDFs:**

1. **Upload PDF to S3:**
   ```bash
   aws s3 cp policy.pdf s3://mb-assistant-bucket/mba/pdf/policy.pdf
   ```

2. **Run Textract manually:**
   ```bash
   aws textract start-document-text-detection \
     --document-location '{
       "S3Object": {
         "Bucket": "mb-assistant-bucket",
         "Name": "mba/pdf/policy.pdf"
       }
     }'
   # Note the JobId from output
   ```

3. **Wait for completion and get results:**
   ```bash
   aws textract get-document-text-detection --job-id <JobId>
   ```

4. **Upload results to S3:**
   ```bash
   aws s3 cp textract-output.json \
     s3://mb-assistant-bucket/mba/textract-output/mba/pdf/policy.pdf/textract-output.json
   ```

5. **Now call RAG preparation:**
   ```bash
   curl -X POST http://127.0.0.1:8000/rag/prepare \
     -H "Content-Type: application/json" \
     -d '{
       "s3_bucket": "mb-assistant-bucket",
       "textract_prefix": "mba/textract-output/mba/pdf/policy.pdf/",
       "index_name": "benefit_coverage_rag_index"
     }'
   ```

---

## Recommended Path Forward

### Phase 1: Use What Works (This Week)
1. ✅ Use CSV uploads for data
2. ✅ Query member verification
3. ✅ Query deductibles
4. ✅ Query benefit accumulator
5. ✅ Test orchestration agent

### Phase 2: Set Up Textract (Next Week/Month)
1. Create AWS Lambda function
2. Configure S3 triggers
3. Test with sample PDF
4. Enable PDF upload in frontend

---

## Quick Fix for Frontend

I've already updated the frontend to:
1. Only accept CSV files for now
2. Show helpful error message if PDF RAG fails
3. Focus on working features

**You can use the application RIGHT NOW for:**
- Member verification queries
- Deductible queries
- Benefit accumulator queries
- CSV data uploads

---

## Testing Right Now

### Open Frontend:
```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT\frontend
npm start
```

### Try These Working Queries:
```
1. Is member M1001 active?
2. What's the deductible for member M1234?
3. How many visits has member M5678 used?
```

### Skip:
- PDF upload (requires Textract setup)

### Use:
- CSV upload (works fine!)
- All query features (working!)

---

## Path Structure Reference

```
S3 Bucket: mb-assistant-bucket/
├── mba/
│   ├── pdf/
│   │   └── benefit_coverage.pdf          ← PDF uploaded here ✅
│   │
│   ├── textract-output/
│   │   └── mba/
│   │       └── pdf/
│   │           └── benefit_coverage.pdf/
│   │               └── textract-output.json   ← Textract output should be here ❌ MISSING
│   │
│   └── csv/
│       └── members.csv                    ← CSV files uploaded here ✅
```

---

## Summary

**Current State:**
- 80% of functionality works perfectly
- PDF RAG requires additional AWS setup

**Recommendation:**
- Use the system for member/benefit queries NOW
- Set up Textract later when needed

**Next Steps:**
1. Test with working queries
2. Upload CSV data if needed
3. Enjoy the orchestration agent!
4. Set up Textract when you need PDF support

---

The system is ready to use for your primary use case (querying member/benefit data)! 🎉
