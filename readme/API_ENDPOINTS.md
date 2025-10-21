# MBA System API Endpoints

Complete reference for all REST API endpoints in the MBA (Medical Benefits Administration) system.

**Base URL**: `http://localhost:8000` (development)
**API Version**: `0.2.0`
**Framework**: FastAPI

---

## Table of Contents

- [Health Check](#health-check)
- [Upload Endpoints](#upload-endpoints)
- [CSV Ingestion Endpoints](#csv-ingestion-endpoints)
- [Member Verification Endpoints](#member-verification-endpoints)
- [Deductible/OOP Lookup Endpoints](#deductibleoop-lookup-endpoints)
- [Benefit Accumulator Lookup Endpoints](#benefit-accumulator-lookup-endpoints)
- [Benefit Coverage RAG Endpoints](#benefit-coverage-rag-endpoints)
- [Intent Identification Endpoints](#intent-identification-endpoints)
- [Orchestration Endpoints](#orchestration-endpoints)
- [Quick Reference Table](#quick-reference-table)

---

## Health Check

### GET `/health`
Check service health and database connectivity.

**Tags**: `Health`

**Response Model**: `HealthResponse`

**Response Example**:
```json
{
  "status": "healthy",
  "services": {
    "s3_client": "initialized",
    "file_processor": "initialized",
    "duplicate_detector": "initialized",
    "rds_client": "initialized",
    "csv_ingestor": "initialized",
    "verification_agent": "initialized",
    "deductible_oop_agent": "initialized",
    "benefit_accumulator_agent": "initialized",
    "benefit_coverage_rag_agent": "initialized",
    "intent_identification_agent": "initialized",
    "orchestration_agent": "initialized"
  },
  "database_connected": true
}
```

**Status Codes**:
- `200 OK`: Service is healthy

---

## Upload Endpoints

### POST `/upload/single`
Upload a single file to S3 with duplicate detection.

**Tags**: `Upload`

**Request**: Multipart form-data
- `file`: File to upload (required)

**Response Model**: `UploadResponse`

**Response Example**:
```json
{
  "success": true,
  "s3_uri": "s3://mb-assistant-bucket/mba/pdf/document.pdf",
  "file_name": "document.pdf",
  "document_type": "pdf",
  "is_duplicate": false,
  "duplicate_of": null,
  "content_hash": "abc123def456"
}
```

**Status Codes**:
- `200 OK`: File uploaded successfully
- `400 Bad Request`: File validation failed
- `503 Service Unavailable`: Services not initialized

---

### POST `/upload/multi`
Upload multiple files to S3 in batch.

**Tags**: `Upload`

**Request**: Multipart form-data
- `files`: List of files to upload (required)

**Response Model**: `MultiUploadResponse`

**Response Example**:
```json
{
  "total": 3,
  "successful": 2,
  "failed": 1,
  "uploads": [
    {
      "success": true,
      "s3_uri": "s3://mb-assistant-bucket/mba/pdf/file1.pdf",
      "file_name": "file1.pdf",
      "document_type": "pdf",
      "is_duplicate": false,
      "duplicate_of": null,
      "content_hash": "abc123"
    },
    {
      "success": true,
      "s3_uri": "s3://mb-assistant-bucket/mba/pdf/file2.pdf",
      "file_name": "file2.pdf",
      "document_type": "pdf",
      "is_duplicate": true,
      "duplicate_of": ["s3://mb-assistant-bucket/mba/pdf/file1.pdf"],
      "content_hash": "def456"
    }
  ],
  "errors": [
    {
      "file_name": "file3.pdf",
      "error": "File validation failed"
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Batch upload completed (check individual results)
- `400 Bad Request`: No files provided
- `503 Service Unavailable`: Services not initialized

---

## CSV Ingestion Endpoints

### POST `/ingest/file`
Ingest single CSV file into RDS database.

**Tags**: `Ingestion`

**Request Model**: `IngestFileRequest`

**Request Body Example**:
```json
{
  "file_path": "data/csv/MemberData.csv",
  "table_name": "members",
  "update_schema": true
}
```

**Response Model**: `IngestResponse`

**Response Example**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Ingestion job queued for MemberData.csv"
}
```

**Status Codes**:
- `200 OK`: Job queued successfully
- `404 Not Found`: CSV file not found
- `503 Service Unavailable`: Ingestion service not initialized

---

### POST `/ingest/directory`
Ingest all CSV files from a directory.

**Tags**: `Ingestion`

**Request Model**: `IngestDirectoryRequest`

**Request Body Example**:
```json
{
  "directory_path": "data/csv",
  "file_pattern": "*.csv",
  "continue_on_error": true
}
```

**Response Model**: `IngestResponse`

**Response Example**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "queued",
  "message": "Directory ingestion queued for data/csv"
}
```

**Status Codes**:
- `200 OK`: Job queued successfully
- `404 Not Found`: Directory not found
- `503 Service Unavailable`: Ingestion service not initialized

---

### GET `/ingest/status/{job_id}`
Get status of ingestion job.

**Tags**: `Ingestion`

**Path Parameters**:
- `job_id` (string): Job identifier from ingest response

**Response Model**: `IngestStatusResponse`

**Response Example**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "started_at": "2025-10-15T14:30:00",
  "completed_at": "2025-10-15T14:32:15",
  "results": {
    "rows_inserted": 1000,
    "table_name": "members",
    "schema_updated": true
  },
  "error": null
}
```

**Status Codes**:
- `200 OK`: Job status retrieved
- `404 Not Found`: Job ID not found

---

## Member Verification Endpoints

### POST `/verify/member`
Verify a single member identity.

**Tags**: `Verification`

**Request Model**: `VerificationRequest`

**Request Body Example**:
```json
{
  "member_id": "M1001",
  "dob": "2005-05-23",
  "name": "Brandi Kim"
}
```

**Response Example**:
```json
{
  "valid": true,
  "member_id": "M1001",
  "name": "Brandi Kim",
  "dob": "2005-05-23"
}
```

**Status Codes**:
- `200 OK`: Verification completed
- `400 Bad Request`: Missing required parameters
- `500 Internal Server Error`: Verification failed
- `503 Service Unavailable`: Verification service not initialized

---

### POST `/verify/batch`
Verify multiple members in batch.

**Tags**: `Verification`

**Request Model**: `BatchVerificationRequest`

**Request Body Example**:
```json
{
  "members": [
    {"member_id": "M1001"},
    {"member_id": "M1002", "dob": "1961-04-08"},
    {"member_id": "M9999"}
  ]
}
```

**Response Example**:
```json
{
  "results": [
    {
      "valid": true,
      "member_id": "M1001",
      "name": "Brandi Kim",
      "dob": "2005-05-23"
    },
    {
      "valid": true,
      "member_id": "M1002",
      "name": "Dawn Brown",
      "dob": "1961-04-08"
    },
    {
      "valid": false,
      "message": "Authentication failed"
    }
  ],
  "total": 3
}
```

**Status Codes**:
- `200 OK`: Batch verification completed
- `500 Internal Server Error`: Batch verification failed
- `503 Service Unavailable`: Verification service not initialized

---

## Deductible/OOP Lookup Endpoints

### POST `/lookup/deductible-oop`
Lookup deductible and out-of-pocket information for a member.

**Tags**: `Lookup`

**Request Model**: `DeductibleOOPRequest`

**Request Body Example**:
```json
{
  "member_id": "M1001",
  "plan_type": "individual",
  "network": "ppo"
}
```

**Response Example**:
```json
{
  "found": true,
  "member_id": "M1001",
  "individual": {
    "ppo": {
      "deductible": 2683,
      "deductible_met": 1840,
      "deductible_remaining": 843,
      "oop": 1120,
      "oop_met": 495,
      "oop_remaining": 625
    },
    "par": {...},
    "oon": {...}
  },
  "family": {...}
}
```

**Status Codes**:
- `200 OK`: Lookup completed
- `400 Bad Request`: Missing member_id
- `500 Internal Server Error`: Lookup failed
- `503 Service Unavailable`: Deductible/OOP service not initialized

---

## Benefit Accumulator Lookup Endpoints

### POST `/lookup/benefit-accumulator`
Lookup benefit accumulator information for a member.

**Tags**: `Lookup`

**Request Model**: `BenefitAccumulatorRequest`

**Request Body Example**:
```json
{
  "member_id": "M1001",
  "service": "Massage Therapy"
}
```

**Response Example**:
```json
{
  "found": true,
  "member_id": "M1001",
  "services": {
    "Massage Therapy": {
      "used": 4,
      "limit": 12,
      "remaining": 8
    },
    "Chiropractic": {
      "used": 8,
      "limit": 20,
      "remaining": 12
    }
  }
}
```

**Status Codes**:
- `200 OK`: Lookup completed
- `400 Bad Request`: Missing member_id
- `500 Internal Server Error`: Lookup failed
- `503 Service Unavailable`: Benefit accumulator service not initialized

---

## Benefit Coverage RAG Endpoints

### POST `/rag/prepare`
Prepare RAG pipeline from Textract output in S3.

**Tags**: `RAG`

**Request Model**: `RAGPrepareRequest`

**Request Body Example**:
```json
{
  "s3_bucket": "mb-assistant-bucket",
  "textract_prefix": "mba/textract-output/mba/pdf/policy.pdf/job-123/",
  "index_name": "benefit_coverage_rag_index",
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

**Response Example**:
```json
{
  "success": true,
  "message": "Processed 10 docs into 45 chunks",
  "chunks_count": 45,
  "doc_count": 10,
  "index_name": "benefit_coverage_rag_index"
}
```

**Status Codes**:
- `200 OK`: Pipeline prepared successfully
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Preparation failed
- `503 Service Unavailable`: RAG service not initialized

---

### POST `/rag/query`
Query benefit coverage documents using RAG.

**Tags**: `RAG`

**Request Model**: `RAGQueryRequest`

**Request Body Example**:
```json
{
  "question": "Is massage therapy covered?",
  "index_name": "benefit_coverage_rag_index",
  "k": 5
}
```

**Response Example**:
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
        "page": 15,
        "section_title": "Therapy Services"
      }
    }
  ],
  "question": "Is massage therapy covered?",
  "retrieved_docs_count": 3
}
```

**Status Codes**:
- `200 OK`: Query completed successfully
- `400 Bad Request`: Invalid parameters
- `500 Internal Server Error`: Query failed
- `503 Service Unavailable`: RAG service not initialized

---

## Intent Identification Endpoints

### POST `/intent/identify`
Identify user intent from query for intelligent routing.

**Tags**: `Intent`

**Request Model**: `IntentIdentificationRequest`

**Request Body Example**:
```json
{
  "query": "Is member M1001 active?",
  "context": {}
}
```

**Response Example**:
```json
{
  "success": true,
  "intent": "member_verification",
  "confidence": 0.95,
  "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
  "extracted_entities": {
    "member_id": "M1001",
    "query_type": "status"
  },
  "suggested_agent": "MemberVerificationAgent",
  "fallback_intent": "general_inquiry",
  "pattern_matches": {
    "member_verification": 2,
    "deductible_oop": 0,
    "benefit_accumulator": 0,
    "benefit_coverage_rag": 0,
    "local_rag": 0,
    "general_inquiry": 0
  },
  "query": "Is member M1001 active?"
}
```

**Status Codes**:
- `200 OK`: Intent identified
- `400 Bad Request`: Invalid query
- `500 Internal Server Error`: Intent identification failed
- `503 Service Unavailable`: Intent service not initialized

---

### POST `/intent/identify-batch`
Identify intents for multiple queries in batch.

**Tags**: `Intent`

**Request Model**: `BatchIntentIdentificationRequest`

**Request Body Example**:
```json
{
  "queries": [
    "Is member M1001 active?",
    "What is the deductible for member M1234?",
    "How many massage visits has member M5678 used?"
  ],
  "context": {}
}
```

**Response Example**:
```json
{
  "results": [
    {
      "success": true,
      "intent": "member_verification",
      "confidence": 0.95,
      ...
    },
    {
      "success": true,
      "intent": "deductible_oop",
      "confidence": 0.90,
      ...
    },
    {
      "success": true,
      "intent": "benefit_accumulator",
      "confidence": 0.98,
      ...
    }
  ],
  "total": 3
}
```

**Status Codes**:
- `200 OK`: Batch identification completed
- `500 Internal Server Error`: Batch identification failed
- `503 Service Unavailable`: Intent service not initialized

---

### GET `/intent/supported`
Get list of supported intent categories.

**Tags**: `Intent`

**Response Example**:
```json
{
  "intents": [
    "member_verification",
    "deductible_oop",
    "benefit_accumulator",
    "benefit_coverage_rag",
    "local_rag",
    "general_inquiry"
  ],
  "agent_mapping": {
    "member_verification": "MemberVerificationAgent",
    "deductible_oop": "DeductibleOOPAgent",
    "benefit_accumulator": "BenefitAccumulatorAgent",
    "benefit_coverage_rag": "BenefitCoverageRAGAgent",
    "local_rag": "LocalRAGAgent",
    "general_inquiry": "None"
  }
}
```

**Status Codes**:
- `200 OK`: Supported intents retrieved
- `500 Internal Server Error`: Failed to retrieve
- `503 Service Unavailable`: Intent service not initialized

---

## Orchestration Endpoints

### POST `/orchestrate/query`
Process a user query through intelligent multi-agent orchestration.

**Tags**: `Orchestration`

**Request Model**: `OrchestrationRequest`

**Request Body Example**:
```json
{
  "query": "Is member M1001 active?",
  "context": {},
  "preserve_history": false
}
```

**Response Example**:
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
    "dob": "1990-01-01",
    "status": "active"
  },
  "query": "Is member M1001 active?",
  "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
  "extracted_entities": {
    "member_id": "M1001",
    "query_type": "status"
  }
}
```

**Status Codes**:
- `200 OK`: Query orchestrated successfully
- `400 Bad Request`: Invalid query
- `500 Internal Server Error`: Orchestration failed
- `503 Service Unavailable`: Orchestration service not initialized

---

### POST `/orchestrate/batch`
Process multiple queries through orchestration in batch.

**Tags**: `Orchestration`

**Request Model**: `BatchOrchestrationRequest`

**Request Body Example**:
```json
{
  "queries": [
    "Is member M1001 active?",
    "What is the deductible for member M1234?",
    "How many massage therapy visits has member M5678 used?",
    "Is acupuncture covered under the plan?"
  ],
  "context": {}
}
```

**Response Example**:
```json
{
  "results": [
    {
      "success": true,
      "intent": "member_verification",
      "confidence": 0.95,
      "agent": "MemberVerificationAgent",
      "result": {...},
      "query": "Is member M1001 active?"
    },
    {...},
    {...},
    {...}
  ],
  "total": 4,
  "successful": 4,
  "failed": 0,
  "intents": {
    "member_verification": 1,
    "deductible_oop": 1,
    "benefit_accumulator": 1,
    "benefit_coverage_rag": 1
  }
}
```

**Status Codes**:
- `200 OK`: Batch orchestration completed
- `500 Internal Server Error`: Batch orchestration failed
- `503 Service Unavailable`: Orchestration service not initialized

---

### GET `/orchestrate/agents`
Get list of available specialized agents.

**Tags**: `Orchestration`

**Response Example**:
```json
{
  "agents": [
    "IntentIdentificationAgent",
    "MemberVerificationAgent",
    "DeductibleOOPAgent",
    "BenefitAccumulatorAgent",
    "BenefitCoverageRAGAgent",
    "LocalRAGAgent"
  ],
  "total_agents": 6,
  "orchestration_enabled": true
}
```

**Status Codes**:
- `200 OK`: Agents list retrieved
- `500 Internal Server Error`: Failed to retrieve
- `503 Service Unavailable`: Orchestration service not initialized

---

### GET `/orchestrate/history`
Get conversation history for the current orchestration session.

**Tags**: `Orchestration`

**Response Example**:
```json
{
  "history": [
    {
      "query": "Is member M1001 active?",
      "intent": "member_verification",
      "confidence": 0.95,
      "agent": "MemberVerificationAgent",
      "success": true,
      "timestamp": null
    },
    {
      "query": "What is their deductible?",
      "intent": "deductible_oop",
      "confidence": 0.88,
      "agent": "DeductibleOOPAgent",
      "success": true,
      "timestamp": null
    }
  ],
  "total_interactions": 2
}
```

**Status Codes**:
- `200 OK`: History retrieved
- `500 Internal Server Error`: Failed to retrieve
- `503 Service Unavailable`: Orchestration service not initialized

---

### DELETE `/orchestrate/history`
Clear conversation history for the current orchestration session.

**Tags**: `Orchestration`

**Response Example**:
```json
{
  "success": true,
  "message": "Conversation history cleared"
}
```

**Status Codes**:
- `200 OK`: History cleared
- `500 Internal Server Error`: Failed to clear
- `503 Service Unavailable`: Orchestration service not initialized

---

## Quick Reference Table

| Method | Endpoint | Purpose | Tags |
|--------|----------|---------|------|
| `GET` | `/health` | Service health check | Health |
| `POST` | `/upload/single` | Upload single file to S3 | Upload |
| `POST` | `/upload/multi` | Upload multiple files to S3 | Upload |
| `POST` | `/ingest/file` | Ingest single CSV file | Ingestion |
| `POST` | `/ingest/directory` | Ingest CSV directory | Ingestion |
| `GET` | `/ingest/status/{job_id}` | Get ingestion status | Ingestion |
| `POST` | `/verify/member` | Verify member identity | Verification |
| `POST` | `/verify/batch` | Batch member verification | Verification |
| `POST` | `/lookup/deductible-oop` | Lookup deductible/OOP | Lookup |
| `POST` | `/lookup/benefit-accumulator` | Lookup benefit accumulator | Lookup |
| `POST` | `/rag/prepare` | Prepare RAG pipeline | RAG |
| `POST` | `/rag/query` | Query benefit coverage | RAG |
| `POST` | `/intent/identify` | Identify query intent | Intent |
| `POST` | `/intent/identify-batch` | Batch intent identification | Intent |
| `GET` | `/intent/supported` | Get supported intents | Intent |
| `POST` | `/orchestrate/query` | Orchestrate single query | Orchestration |
| `POST` | `/orchestrate/batch` | Orchestrate batch queries | Orchestration |
| `GET` | `/orchestrate/agents` | Get available agents | Orchestration |
| `GET` | `/orchestrate/history` | Get conversation history | Orchestration |
| `DELETE` | `/orchestrate/history` | Clear conversation history | Orchestration |

---

## API Categories

### 📋 Core Services (3 endpoints)
- Health Check
- File Upload
- CSV Ingestion

### 👤 Member Services (2 endpoints)
- Member Verification
- Batch Verification

### 💰 Financial Lookups (2 endpoints)
- Deductible/OOP Lookup
- Benefit Accumulator Lookup

### 📚 RAG Services (2 endpoints)
- RAG Pipeline Preparation
- RAG Query Execution

### 🎯 Intent Classification (3 endpoints)
- Single Intent Identification
- Batch Intent Identification
- Supported Intents List

### 🤖 Orchestration (5 endpoints)
- Single Query Orchestration
- Batch Query Orchestration
- Available Agents List
- Conversation History
- Clear History

---

## Total Endpoints: **20**

**Breakdown by Category:**
- Health: 1
- Upload: 2
- Ingestion: 3
- Verification: 2
- Lookup: 2
- RAG: 2
- Intent: 3
- Orchestration: 5

---

## Testing

### Using cURL

```bash
# Health check
curl http://localhost:8000/health

# Member verification
curl -X POST http://localhost:8000/verify/member \
  -H "Content-Type: application/json" \
  -d '{"member_id": "M1001"}'

# Orchestration
curl -X POST http://localhost:8000/orchestrate/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Is member M1001 active?"}'
```

### Using Python Requests

```python
import requests

# Base URL
base_url = "http://localhost:8000"

# Health check
response = requests.get(f"{base_url}/health")
print(response.json())

# Member verification
response = requests.post(
    f"{base_url}/verify/member",
    json={"member_id": "M1001"}
)
print(response.json())

# Orchestration
response = requests.post(
    f"{base_url}/orchestrate/query",
    json={"query": "Is member M1001 active?"}
)
print(response.json())
```

---

## Interactive API Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These interfaces allow you to:
- Browse all endpoints
- View request/response schemas
- Test endpoints directly in the browser
- Download OpenAPI specification

---

## Running the API Server

```bash
# Method 1: Using uvicorn directly
uvicorn MBA.microservices.api:app --reload --host 0.0.0.0 --port 8000

# Method 2: Using Python module
python -m MBA.microservices.api

# Method 3: From script
python src/MBA/microservices/api.py
```

---

## Authentication

Currently, the API does not require authentication. For production deployment, consider adding:
- API key authentication
- JWT tokens
- OAuth 2.0
- AWS IAM authentication

---

## Rate Limiting

No rate limiting is currently implemented. For production, consider:
- Per-IP rate limiting
- Per-API-key rate limiting
- Request throttling

---

## Error Handling

All endpoints follow consistent error response format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `200 OK`: Success
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server-side error
- `503 Service Unavailable`: Service not initialized

---

## Related Documentation

- [Agent READMEs](src/MBA/agents/)
- [Database ETL Documentation](src/MBA/etl/)
- [Streamlit UI Documentation](src/MBA/ui/)

---

Last Updated: 2025-10-15
API Version: 0.2.0
