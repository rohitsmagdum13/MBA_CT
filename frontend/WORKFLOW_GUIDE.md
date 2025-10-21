# MBA Frontend - Complete Workflow Guide

## Overview

The frontend has been updated to integrate with your orchestration agent and support intelligent file uploads with RAG (Retrieval-Augmented Generation) preparation.

---

## Architecture

```
User → Upload File (PDF/CSV) → Backend Processing → Query with AI → Orchestration Agent → Specialized Agent → Response
```

### Key Features:
1. **Smart File Upload**: PDF files are automatically processed through RAG pipeline, CSV files are uploaded to S3
2. **Intelligent Routing**: Queries are automatically routed to the correct agent based on intent
3. **Rich Response Display**: Different response formats for different agent types
4. **Progress Tracking**: Real-time upload and processing status

---

## How It Works

### Step 1: Upload Document (Optional but Recommended)

**Supported File Types:**
- **PDF Files**: Policy documents, benefit coverage documents
  - Auto-processed through AWS Textract
  - Chunked and indexed for RAG querying
  - Endpoint: `/rag/upload-and-prepare`

- **CSV Files**: Member data, benefit accumulator data, deductible data
  - Uploaded to S3 with duplicate detection
  - Categorized by document type
  - Endpoint: `/upload/single`

**What Happens:**
```
PDF Upload Flow:
1. File selected → Validation
2. Upload to S3 (mba/pdf/)
3. Textract processing triggered
4. Text extraction and chunking
5. Embeddings generated (Bedrock Titan)
6. Indexed in Qdrant vector store
7. Ready for querying!

CSV Upload Flow:
1. File selected → Validation
2. Hash computation for duplicate detection
3. Document type classification
4. Upload to S3 with metadata
5. Ready for ingestion!
```

### Step 2: Ask Your Question

**The orchestration agent automatically routes your query to the right specialized agent:**

#### Intent: `member_verification`
**Example Queries:**
- "Is member M1001 active?"
- "Verify member M1234 with DOB 1990-01-15"
- "Check if John Doe is an active member"

**Agent:** MemberVerificationAgent
**Response Format:**
```json
{
  "valid": true,
  "member_id": "M1001",
  "name": "John Doe",
  "dob": "1990-01-01",
  "status": "active"
}
```

#### Intent: `deductible_oop`
**Example Queries:**
- "What is the deductible for member M1234?"
- "Show me M5678's out-of-pocket maximum"
- "How much has member M1001 paid towards their deductible?"

**Agent:** DeductibleOOPAgent
**Response Format:**
```json
{
  "found": true,
  "member_id": "M1234",
  "individual": {
    "deductible": 1500,
    "deductible_met": 500,
    "oop_max": 5000,
    "oop_met": 1200
  },
  "family": { ... }
}
```

#### Intent: `benefit_accumulator`
**Example Queries:**
- "How many massage therapy visits has member M5678 used?"
- "What's the benefit usage for M1001?"
- "Show me chiropractic visits for member M1234"

**Agent:** BenefitAccumulatorAgent
**Response Format:**
```json
{
  "found": true,
  "member_id": "M5678",
  "benefits": [
    {
      "service": "Massage Therapy",
      "allowed_limit": 6,
      "used": 3,
      "remaining": 3
    }
  ]
}
```

#### Intent: `benefit_coverage_rag`
**Example Queries:**
- "Is acupuncture covered under the plan?"
- "What are the massage therapy benefits?"
- "Are mental health services covered?"

**Agent:** BenefitCoverageRAGAgent
**Response Format:**
```json
{
  "success": true,
  "answer": "Massage therapy is covered with a limit of 6 visits per calendar year...",
  "sources": [
    {
      "source_id": 1,
      "content": "Massage Therapy: Covered with 6 visit limit...",
      "metadata": {
        "source": "policy.pdf",
        "page": 15
      }
    }
  ]
}
```

---

## API Endpoints Used

### Upload Endpoints

**1. PDF Upload with RAG Preparation**
```
POST /rag/upload-and-prepare
Content-Type: multipart/form-data

Request:
- file: PDF file
- index_name: (optional) "benefit_coverage_rag_index"
- chunk_size: (optional) 1000
- chunk_overlap: (optional) 200

Response:
{
  "success": true,
  "message": "PDF uploaded and RAG pipeline prepared successfully",
  "file_name": "policy.pdf",
  "s3_uri": "s3://mb-assistant-bucket/mba/pdf/policy.pdf",
  "rag_preparation": {
    "success": true,
    "chunks_count": 67,
    "doc_count": 15,
    "index_name": "benefit_coverage_rag_index"
  },
  "query_ready": true
}
```

**2. CSV Upload**
```
POST /upload/single
Content-Type: multipart/form-data

Request:
- file: CSV file

Response:
{
  "success": true,
  "s3_uri": "s3://mb-assistant-bucket/mba/csv/members.csv",
  "file_name": "members.csv",
  "document_type": "csv",
  "is_duplicate": false,
  "content_hash": "abc123..."
}
```

### Query Endpoint

**Orchestration Query**
```
POST /orchestrate/query
Content-Type: application/json

Request:
{
  "query": "Is member M1001 active?",
  "context": {},
  "preserve_history": false
}

Response:
{
  "success": true,
  "intent": "member_verification",
  "confidence": 0.95,
  "agent": "MemberVerificationAgent",
  "result": {
    "valid": true,
    "member_id": "M1001",
    ...
  },
  "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
  "extracted_entities": {
    "member_id": "M1001",
    "query_type": "status"
  }
}
```

---

## Frontend Components

### Upload Section (Step 1)
- File selector with validation
- Upload progress bar
- Success/Error alerts
- Document ready indicator

### Query Section (Step 2)
- Multi-line text input
- Helper text with examples
- Loading state
- Execution time badge

### Response Display
- **Intent & Agent Chips**: Shows which agent handled the query
- **Confidence Score**: AI's confidence in intent classification
- **Reasoning Alert**: Explains why this intent was chosen
- **Formatted Answer**: Custom formatting based on response type
- **Extracted Entities**: Shows what the AI extracted from the query

---

## Running the Application

### 1. Start Backend (Required)

```bash
# Terminal 1 - Start FastAPI backend
cd c:\Users\ROHIT\Work\HMA\MBA_CT
python -m uvicorn src.MBA.microservices.api:app --reload --host 0.0.0.0 --port 8000
```

**Backend should be running at:** `http://127.0.0.1:8000`

### 2. Start Frontend

```bash
# Terminal 2 - Start React frontend
cd c:\Users\ROHIT\Work\HMA\MBA_CT\frontend
npm install  # First time only
npm start
```

**Frontend will open at:** `http://localhost:3000`

---

## Testing the Workflow

### Test 1: PDF Upload + RAG Query

1. **Upload a PDF:**
   - Click "Choose File (PDF/CSV)"
   - Select a benefit policy PDF
   - Click "Upload & Process"
   - Wait for "Document Ready for Querying" indicator

2. **Query the PDF:**
   - Enter: "Is massage therapy covered?"
   - Click "Get Answer"
   - See RAG-powered response with sources

### Test 2: CSV Upload + Member Query

1. **Upload CSV:**
   - Select a member data CSV
   - Click "Upload & Process"
   - Confirm upload success

2. **Query Member Data:**
   - Enter: "Is member M1001 active?"
   - See verification result with member details

### Test 3: Benefit Accumulator Query

**Query:**
```
How many massage therapy visits has member M5678 used?
```

**Expected Response:**
- Intent: `benefit_accumulator`
- Agent: `BenefitAccumulatorAgent`
- Shows visit usage and remaining visits

### Test 4: Deductible Query

**Query:**
```
What is the deductible for member M1234?
```

**Expected Response:**
- Intent: `deductible_oop`
- Agent: `DeductibleOOPAgent`
- Shows deductible amounts and met amounts

---

## Environment Variables

Edit `frontend/.env`:

```env
# Backend API URL
REACT_APP_API_URL=http://127.0.0.1:8000

# Optional: Override specific endpoints
REACT_APP_FEEDBACK_NODE_API_URL=http://127.0.0.1:5000/api/feedback
```

---

## Troubleshooting

### Issue: Upload fails for PDF

**Check:**
1. Is backend running on port 8000?
2. Is AWS Textract configured?
3. Check backend logs for errors

**Solution:**
```bash
# Check backend health
curl http://127.0.0.1:8000/health
```

### Issue: Query returns error

**Common causes:**
1. **Database not populated**: Upload CSV data first
2. **Member ID not found**: Check database for valid member IDs
3. **RAG index empty**: Upload and process a PDF first

**Check backend logs:**
```bash
# Look for errors in backend terminal
# Check database connectivity
# Verify agent initialization
```

### Issue: CORS errors

**Solution:**
Backend already has CORS configured for `http://localhost:3000`.
If using a different port, update `src/MBA/microservices/api.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Add your port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Code Structure

```
frontend/
├── src/
│   ├── App.js              # Main component with all logic
│   │   ├── handleFileChange()      # File selection
│   │   ├── handleFileUpload()      # Upload with RAG preparation
│   │   ├── handleSubmit()          # Query orchestration
│   │   ├── formatResultData()      # Response formatting
│   │   └── renderMemberBenefitTab() # UI rendering
│   ├── FeedbackControl.js  # Feedback component (future use)
│   ├── DocumentViewer.js   # Document viewer (future use)
│   └── index.js            # React entry point
└── public/
    └── index.html          # HTML template
```

---

## Next Steps

1. **Test all workflows** with real data
2. **Add error boundaries** for better error handling
3. **Implement feedback system** using FeedbackControl component
4. **Add conversation history** using preserve_history flag
5. **Create document library** using DocumentViewer component

---

## Support

**Frontend Issues:**
- Check browser console for errors
- Verify API endpoints in Network tab
- Check `.env` configuration

**Backend Issues:**
- Check FastAPI logs in terminal
- Verify database connection
- Test endpoints with Swagger UI: `http://127.0.0.1:8000/docs`

**Agent Issues:**
- Check agent initialization in `/health` endpoint
- Verify AWS credentials and Bedrock access
- Check RDS database connectivity

---

**Happy Querying! 🚀**
