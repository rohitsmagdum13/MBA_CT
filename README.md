# MBA (Medical Benefits Administration) System

## 🏥 Complete End-to-End Documentation

**Version**: 2.0.0
**Last Updated**: October 15, 2025
**Architecture**: Multi-Agent AI System with AWS Integration

---

## 📑 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Technology Stack](#technology-stack)
4. [System Components](#system-components)
5. [Data Flow Diagrams](#data-flow-diagrams)
6. [Agent Architecture](#agent-architecture)
7. [Setup & Installation](#setup--installation)
8. [Configuration](#configuration)
9. [Usage Workflows](#usage-workflows)
10. [API Reference](#api-reference)
11. [Database Schema](#database-schema)
12. [Testing](#testing)
13. [Deployment](#deployment)
14. [Troubleshooting](#troubleshooting)
15. [Project Structure](#project-structure)
16. [Development Guide](#development-guide)

---

## System Overview

The **MBA (Medical Benefits Administration) System** is an intelligent, AI-powered platform for managing healthcare benefits information. It combines multiple AWS services with advanced AI agents to provide:

- 🤖 **AI-Powered Query Processing**: Natural language understanding with AWS Bedrock Claude Sonnet 4.5
- 👤 **Member Management**: Identity verification and eligibility checking
- 💰 **Financial Tracking**: Deductible and out-of-pocket maximum tracking
- 📊 **Benefit Accumulation**: Service usage tracking (massage, chiropractic, etc.)
- 📚 **RAG-based Q&A**: Policy coverage questions using vector databases
- 🎯 **Intelligent Orchestration**: Multi-agent routing and coordination
- 📁 **Document Processing**: PDF/CSV upload, OCR with Textract
- 🗄️ **Database Integration**: RDS MySQL with automated ETL

---

## Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                          MBA SYSTEM ARCHITECTURE                              │
└───────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────┐         ┌──────────────────┐                        │
│   │   Streamlit UI   │         │  REST API Clients│                        │
│   │  (Web Interface) │         │  (curl, Postman) │                        │
│   │   Port: 8501     │         │                  │                        │
│   └────────┬─────────┘         └────────┬─────────┘                        │
│            │                             │                                  │
└────────────┼─────────────────────────────┼──────────────────────────────────┘
             │                             │
             ▼                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          API LAYER (FastAPI)                                │
│                           Port: 8000                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Upload    │  │  Ingestion  │  │     RAG     │  │    Agents   │      │
│  │  Endpoints  │  │  Endpoints  │  │  Endpoints  │  │  Endpoints  │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
│         │                │                │                │              │
└─────────┼────────────────┼────────────────┼────────────────┼──────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SERVICE LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   S3 Client  │  │ File Processor│  │ CSV Ingestor │  │  AI Agents   │  │
│  │   Upload     │  │   Duplicate   │  │ ETL Pipeline │  │ Orchestration│  │
│  │   Storage    │  │   Detection   │  │ Schema Mgmt  │  │   Routing    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │                 │           │
└─────────┼─────────────────┼─────────────────┼─────────────────┼───────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AWS SERVICES                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Amazon S3  │  │   Textract   │  │  RDS MySQL   │  │   Bedrock    │  │
│  │   Document   │  │     OCR      │  │   Database   │  │    Claude    │  │
│  │   Storage    │  │  Extraction  │  │    Tables    │  │  Sonnet 4.5  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐                                        │
│  │   Pinecone   │  │     FAISS    │                                        │
│  │    Vector    │  │    Vector    │                                        │
│  │   Database   │  │   Database   │                                        │
│  └──────────────┘  └──────────────┘                                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI AGENT LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                     ┌────────────────────────┐                              │
│                     │  Orchestration Agent   │ ◄─── Entry Point            │
│                     │  (AI Router)           │                              │
│                     └────────┬───────────────┘                              │
│                              │                                              │
│              ┌───────────────┼───────────────┐                              │
│              │               │               │                              │
│              ▼               ▼               ▼                              │
│  ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐              │
│  │    Member        │ │  Deductible  │ │     Benefit      │              │
│  │  Verification    │ │  /OOP Agent  │ │  Accumulator     │              │
│  │     Agent        │ │              │ │     Agent        │              │
│  └──────────────────┘ └──────────────┘ └──────────────────┘              │
│                                                                              │
│  ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐              │
│  │    Benefit       │ │    Local     │ │     Intent       │              │
│  │  Coverage RAG    │ │  RAG Agent   │ │  Identification  │              │
│  │     Agent        │ │              │ │     Agent        │              │
│  └──────────────────┘ └──────────────┘ └──────────────────┘              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### **Backend Framework**
- **FastAPI** - High-performance REST API framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation and serialization

### **AI & ML**
- **AWS Bedrock** - Claude Sonnet 4.5 foundation model
- **Strands Framework** - AI agent orchestration
- **LangChain** - RAG pipeline construction
- **Pinecone/FAISS** - Vector databases for semantic search

### **AWS Services**
- **Amazon S3** - Document storage
- **AWS Textract** - OCR and document analysis
- **Amazon RDS (MySQL)** - Relational database
- **AWS IAM** - Authentication and authorization
- **AWS Lambda** - Serverless function execution (optional)

### **Database & ORM**
- **MySQL 8.0** - Primary database
- **SQLAlchemy** - Python ORM
- **PyMySQL** - MySQL driver

### **Frontend**
- **Streamlit** - Interactive web UI
- **Python 3.11+** - Programming language

### **Data Processing**
- **Pandas** - Data manipulation
- **NumPy** - Numerical computing
- **OpenPyXL** - Excel file handling

### **Development Tools**
- **UV** - Modern Python package manager
- **pytest** - Testing framework
- **Black** - Code formatter
- **Ruff** - Fast Python linter

---

## System Components

### 1. **Upload & Storage System** 📁

**Purpose**: Handle document uploads with intelligent routing and duplicate detection.

**Components**:
- `S3Client` - AWS S3 upload management
- `FileProcessor` - Document type classification
- `DuplicateDetector` - SHA-256 content hashing

**Features**:
- Multi-format support (PDF, Word, Excel, CSV, Images)
- Automatic document type routing
- Content-based duplicate detection
- Server-side encryption (AES256)

---

### 2. **ETL & Data Ingestion System** 🔄

**Purpose**: Automated CSV data ingestion into RDS MySQL.

**Components**:
- `CSVIngestor` - CSV file processing
- `SchemaManager` - Dynamic table creation
- `SchemaInferrer` - Automatic schema detection
- `AuditWriter` - Change tracking

**Features**:
- Automatic schema inference from CSV headers
- Table creation with appropriate data types
- Duplicate detection on ingestion
- Audit logging for all changes
- Transposed table support

---

### 3. **AI Agent System** 🤖

**Purpose**: Intelligent query processing with multi-agent orchestration.

#### **3.1 Orchestration Agent** (Entry Point)

**Role**: Routes queries to appropriate specialized agents.

**Workflow**:
```
User Query
    │
    ▼
analyze_query Tool
    ├─ Classify intent
    ├─ Extract entities (member_id, service, etc.)
    └─ Determine confidence
    │
    ▼
route_to_agent Tool
    ├─ Select specialized agent
    ├─ Execute agent workflow
    └─ Capture results
    │
    ▼
format_response Tool
    ├─ Format for user
    └─ Return structured response
```

**Intents**:
- `member_verification` → Member Verification Agent
- `deductible_oop` → Deductible/OOP Agent
- `benefit_accumulator` → Benefit Accumulator Agent
- `benefit_coverage_rag` → Benefit Coverage RAG Agent
- `local_rag` → Local RAG Agent
- `general_inquiry` → Direct response

---

#### **3.2 Member Verification Agent** 👤

**Purpose**: Validate member identity and eligibility.

**Database**: `memberdata` table

**Query Parameters**:
- `member_id` - Member identifier (e.g., M1001)
- `dob` - Date of birth (YYYY-MM-DD)
- `name` - Full name

**Sample Query**:
```sql
SELECT member_id, CONCAT(first_name, ' ', last_name) AS name, dob
FROM memberdata
WHERE member_id = :member_id AND dob = :dob
LIMIT 1
```

**Response**:
```json
{
  "valid": true,
  "member_id": "M1001",
  "name": "Brandi Kim",
  "dob": "2005-05-23"
}
```

---

#### **3.3 Deductible/OOP Agent** 💰

**Purpose**: Retrieve deductible and out-of-pocket maximum information.

**Database**: `deductibles_oop` table (transposed format)

**Structure**:
- Individual/Family plans
- PPO/PAR/OON network levels
- Deductible limits, met amounts, remaining balances
- OOP limits, met amounts, remaining balances

**Sample Query**:
```sql
SELECT Metric, `M1001` as value
FROM deductibles_oop
WHERE `M1001` IS NOT NULL
```

**Response**:
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
    }
  }
}
```

---

#### **3.4 Benefit Accumulator Agent** 📊

**Purpose**: Track benefit usage for specific services.

**Database**: `benefit_accumulator` table (transposed format)

**Services Tracked**:
- Massage Therapy
- Chiropractic Care
- Acupuncture
- Physical Therapy

**Metrics**:
- Used count
- Limit count
- Remaining count

**Sample Query**:
```sql
SELECT Metric, `M1001` as value
FROM benefit_accumulator
WHERE `M1001` IS NOT NULL
AND Metric LIKE '%Massage Therapy%'
```

**Response**:
```json
{
  "found": true,
  "member_id": "M1001",
  "services": {
    "Massage Therapy": {
      "used": 4,
      "limit": 12,
      "remaining": 8
    }
  }
}
```

---

#### **3.5 Benefit Coverage RAG Agent** 📚

**Purpose**: Answer policy coverage questions using RAG.

**Technology**:
- Vector Database: Pinecone or FAISS
- Embeddings: AWS Bedrock Titan or OpenAI
- LLM: Claude Sonnet 4.5

**Workflow**:
```
User Question: "Is massage therapy covered?"
    │
    ▼
Generate Embedding
    │
    ▼
Vector Similarity Search (k=5)
    │
    ▼
Retrieve Relevant Chunks
    │
    ▼
Build Context Prompt
    │
    ▼
LLM Generation
    │
    ▼
Return Answer + Sources
```

**Response**:
```json
{
  "success": true,
  "answer": "Massage therapy is covered with a limit of 12 visits per year...",
  "sources": [
    {
      "content": "Massage Therapy: 12 visit limit...",
      "metadata": {"page": 15, "source": "policy.pdf"}
    }
  ]
}
```

---

#### **3.6 Local RAG Agent** 📄

**Purpose**: Query user-uploaded documents.

**Features**:
- Upload PDFs/documents
- Process with Textract OCR
- Store in local vector database (FAISS)
- Query specific documents

**Use Cases**:
- "What does my uploaded document say about coverage?"
- "Search my files for chiropractic information"

---

## Data Flow Diagrams

### **Flow 1: Document Upload & Storage**

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        DOCUMENT UPLOAD FLOW                               │
└───────────────────────────────────────────────────────────────────────────┘

User
  │
  │ 1. Select File
  ▼
┌─────────────────────┐
│   Streamlit UI      │
│   or                │
│   REST API Client   │
└──────────┬──────────┘
           │
           │ 2. POST /upload/single
           │    (multipart/form-data)
           ▼
┌─────────────────────┐
│   FastAPI Handler   │
│   - Validate file   │
│   - Check size      │
│   - Check extension │
└──────────┬──────────┘
           │
           │ 3. Process File
           ▼
┌─────────────────────┐
│  File Processor     │
│  - Classify type    │
│  - Compute SHA-256  │
└──────────┬──────────┘
           │
           │ 4. Check Duplicate
           ▼
┌─────────────────────┐
│ Duplicate Detector  │
│  - Hash lookup      │
│  - Mark if duplicate│
└──────────┬──────────┘
           │
           │ 5. Upload to S3
           ▼
┌─────────────────────┐
│    S3 Client        │
│  - Route to folder  │
│  - Encrypt (AES256) │
│  - Upload           │
└──────────┬──────────┘
           │
           │ 6. Confirm Upload
           ▼
┌─────────────────────┐
│   Amazon S3         │
│  s3://bucket/       │
│    mba/pdf/file.pdf │
└──────────┬──────────┘
           │
           │ 7. Return Response
           ▼
┌─────────────────────┐
│  Upload Response    │
│  - S3 URI           │
│  - Content hash     │
│  - Is duplicate?    │
│  - Document type    │
└─────────────────────┘
```

---

### **Flow 2: CSV Ingestion to RDS**

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         CSV INGESTION FLOW                                │
└───────────────────────────────────────────────────────────────────────────┘

CSV File
  │
  │ 1. Trigger Ingestion
  ▼
┌─────────────────────┐
│  FastAPI Handler    │
│  POST /ingest/file  │
└──────────┬──────────┘
           │
           │ 2. Create Job
           ▼
┌─────────────────────┐
│   Job Queue         │
│   (In-memory)       │
└──────────┬──────────┘
           │
           │ 3. Process CSV
           ▼
┌─────────────────────┐
│   CSV Ingestor      │
│   - Read CSV        │
│   - Parse headers   │
└──────────┬──────────┘
           │
           │ 4. Infer Schema
           ▼
┌─────────────────────┐
│  Schema Inferrer    │
│  - Detect types     │
│  - Create columns   │
└──────────┬──────────┘
           │
           │ 5. Create/Update Table
           ▼
┌─────────────────────┐
│  Schema Manager     │
│  - CREATE TABLE     │
│  - ALTER TABLE      │
└──────────┬──────────┘
           │
           │ 6. Insert Data
           ▼
┌─────────────────────┐
│   Database Client   │
│  - Batch INSERT     │
│  - Commit           │
└──────────┬──────────┘
           │
           │ 7. Store Data
           ▼
┌─────────────────────┐
│    RDS MySQL        │
│  - memberdata       │
│  - deductibles_oop  │
│  - benefit_accum    │
└──────────┬──────────┘
           │
           │ 8. Update Job Status
           ▼
┌─────────────────────┐
│  Job Status         │
│  - Completed        │
│  - Rows inserted    │
└─────────────────────┘
```

---

### **Flow 3: AI Query Processing (Orchestration)**

```
┌───────────────────────────────────────────────────────────────────────────┐
│                    AI QUERY ORCHESTRATION FLOW                            │
└───────────────────────────────────────────────────────────────────────────┘

User Query: "Is member M1001 active?"
  │
  │ 1. Submit Query
  ▼
┌──────────────────────────────────┐
│  POST /orchestrate/query         │
│  {"query": "Is member M1001..."}│
└──────────────┬───────────────────┘
               │
               │ 2. Invoke Orchestration Agent
               ▼
┌──────────────────────────────────┐
│   Orchestration Agent (Wrapper) │
│   - Lazy init Strands agent      │
│   - Build prompt                 │
└──────────────┬───────────────────┘
               │
               │ 3. Tool #1: analyze_query
               ▼
┌──────────────────────────────────┐
│   analyze_query Tool             │
│   ┌──────────────────────┐       │
│   │ Pattern Matching     │       │
│   │ - member_id: M1001   │       │
│   │ - query_type: status │       │
│   └──────────┬───────────┘       │
│              │                    │
│   ┌──────────▼───────────┐       │
│   │ Intent Classification│       │
│   │ - Best: member_verif │       │
│   │ - Confidence: 0.95   │       │
│   └──────────┬───────────┘       │
│              │                    │
│   ┌──────────▼───────────┐       │
│   │ Return Result        │       │
│   │ {intent, entities}   │       │
│   └──────────────────────┘       │
└──────────────┬───────────────────┘
               │
               │ Result cached
               │
               │ 4. Tool #2: route_to_agent
               ▼
┌──────────────────────────────────┐
│   route_to_agent Tool            │
│   ┌──────────────────────┐       │
│   │ Select Agent         │       │
│   │ → MemberVerification │       │
│   └──────────┬───────────┘       │
│              │                    │
│   ┌──────────▼───────────┐       │
│   │ Import Agent         │       │
│   │ from ..member_verif  │       │
│   └──────────┬───────────┘       │
│              │                    │
│   ┌──────────▼───────────┐       │
│   │ Execute Agent        │       │
│   │ verify_member(...)   │       │
│   └──────────┬───────────┘       │
│              │                    │
│              │ Query Database
│              ▼
│         ┌─────────────┐           │
│         │ RDS MySQL   │           │
│         │ memberdata  │           │
│         └──────┬──────┘           │
│                │                  │
│     ┌──────────▼───────────┐     │
│     │ Return Result        │     │
│     │ {valid, member_id,..}│     │
│     └──────────────────────┘     │
└──────────────┬───────────────────┘
               │
               │ Result cached
               │
               │ 5. Tool #3: format_response (optional)
               ▼
┌──────────────────────────────────┐
│   format_response Tool           │
│   - Add emojis                   │
│   - Format nicely                │
└──────────────┬───────────────────┘
               │
               │ 6. Parse cached results
               ▼
┌──────────────────────────────────┐
│   Wrapper._parse_cached_results │
│   - Get from cache               │
│   - Build final response         │
└──────────────┬───────────────────┘
               │
               │ 7. Return to User
               ▼
┌──────────────────────────────────┐
│  Response                        │
│  {                               │
│    "success": true,              │
│    "intent": "member_verif",     │
│    "agent": "MemberVerif...",    │
│    "result": {                   │
│      "valid": true,              │
│      "member_id": "M1001",       │
│      "name": "Brandi Kim",       │
│      "dob": "2005-05-23"         │
│    },                            │
│    "confidence": 0.95            │
│  }                               │
└──────────────────────────────────┘
```

---

### **Flow 4: RAG Query Processing**

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         RAG QUERY FLOW                                    │
└───────────────────────────────────────────────────────────────────────────┘

User Question: "Is massage therapy covered?"
  │
  │ 1. Submit Question
  ▼
┌────────────────────────────┐
│ POST /rag/query            │
│ {"question": "Is massage.."}│
└──────────┬─────────────────┘
           │
           │ 2. Generate Embedding
           ▼
┌────────────────────────────┐
│  Embedding Generator       │
│  (AWS Bedrock Titan or     │
│   OpenAI Embeddings)       │
│  → Vector: [0.12, -0.45,..]│
└──────────┬─────────────────┘
           │
           │ 3. Vector Search
           ▼
┌────────────────────────────┐
│   Vector Database          │
│   (Pinecone or FAISS)      │
│   - Similarity search      │
│   - Retrieve top k=5       │
└──────────┬─────────────────┘
           │
           │ 4. Get Chunks
           ▼
┌────────────────────────────┐
│  Retrieved Chunks          │
│  Chunk 1: "Massage therapy │
│           is covered..."   │
│  Chunk 2: "6 visit limit..│
│  Chunk 3: "Licensed..."    │
│  ...                       │
└──────────┬─────────────────┘
           │
           │ 5. Build Context
           ▼
┌────────────────────────────┐
│  Context Builder           │
│  Prompt: "Answer based on: │
│  <chunk1>                  │
│  <chunk2>                  │
│  Question: Is massage...?" │
└──────────┬─────────────────┘
           │
           │ 6. LLM Generation
           ▼
┌────────────────────────────┐
│   AWS Bedrock Claude       │
│   - Process context        │
│   - Generate answer        │
│   - Cite sources           │
└──────────┬─────────────────┘
           │
           │ 7. Format Response
           ▼
┌────────────────────────────┐
│  Response                  │
│  {                         │
│    "answer": "Massage      │
│      therapy is covered    │
│      with 6 visit limit...",│
│    "sources": [            │
│      {                     │
│        "content": "...",   │
│        "page": 15,         │
│        "source": "policy.pdf"│
│      }                     │
│    ]                       │
│  }                         │
└────────────────────────────┘
```

---

## Setup & Installation

### **Prerequisites**

- Python 3.11 or higher
- AWS Account with configured credentials
- MySQL 8.0 (via RDS or local)
- UV package manager (recommended) or pip

### **1. Clone Repository**

```bash
git clone https://github.com/your-org/MBA_CT.git
cd MBA_CT
```

### **2. Install UV (Modern Package Manager)**

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### **3. Install Dependencies**

```bash
# Using UV (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### **4. Configure Environment**

Create `.env` file in project root:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1

# S3 Configuration
S3_BUCKET_MBA=mb-assistant-bucket
S3_PREFIX_MBA=mba/

# RDS Configuration
RDS_HOST=your-rds-endpoint.rds.amazonaws.com
RDS_PORT=3306
RDS_USER=admin
RDS_PASSWORD=your_password
RDS_DATABASE=mba_database

# AWS Bedrock
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-v2:0

# Pinecone (for RAG)
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=us-west1-gcp

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_FILE=app.log

# Server-Side Encryption
S3_SSE=AES256
```

### **5. Initialize Database**

```bash
# Run database migrations (if applicable)
python -m MBA.etl.init_db

# Or ingest initial CSV data
uv run python -c "
from MBA.services.ingestion.orchestrator import CSVIngestor
ingestor = CSVIngestor()
# Ingest your CSV files
"
```

### **6. Verify Setup**

```bash
# Test database connection
python debug_rds_connection.py

# Test API health
curl http://localhost:8000/health
```

---

## Configuration

### **Environment Variables**

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key | Yes | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Yes | - |
| `AWS_DEFAULT_REGION` | AWS region | Yes | us-east-1 |
| `S3_BUCKET_MBA` | S3 bucket name | Yes | - |
| `S3_PREFIX_MBA` | S3 key prefix | No | mba/ |
| `RDS_HOST` | RDS endpoint | Yes | - |
| `RDS_PORT` | MySQL port | No | 3306 |
| `RDS_USER` | Database user | Yes | - |
| `RDS_PASSWORD` | Database password | Yes | - |
| `RDS_DATABASE` | Database name | Yes | - |
| `BEDROCK_MODEL_ID` | Bedrock model ID | Yes | - |
| `LOG_LEVEL` | Logging level | No | INFO |

### **AWS IAM Permissions Required**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mb-assistant-bucket/*",
        "arn:aws:s3:::mb-assistant-bucket"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "textract:StartDocumentTextDetection",
        "textract:GetDocumentTextDetection"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:*:*:foundation-model/anthropic.claude-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "rds-db:connect"
      ],
      "Resource": "arn:aws:rds-db:*:*:dbuser:*"
    }
  ]
}
```

---

## Usage Workflows

### **Workflow 1: Start the System**

```bash
# Terminal 1: Start FastAPI server
uv run mba-api
# or
uvicorn MBA.microservices.api:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Streamlit UI
uv run mba-app
# or
streamlit run src/MBA/ui/streamlit_app.py

# Access:
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - UI: http://localhost:8501
```

---

### **Workflow 2: Upload Documents**

#### **Via Streamlit UI**:
1. Open http://localhost:8501
2. Go to "Single Upload" or "Multi Upload" tab
3. Select files
4. Click "Upload"
5. View results and S3 URIs

#### **Via API**:
```bash
curl -X POST "http://localhost:8000/upload/single" \
  -F "file=@document.pdf"
```

---

### **Workflow 3: Ingest CSV Data**

#### **Via API**:
```bash
# Single file
curl -X POST "http://localhost:8000/ingest/file" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "data/csv/MemberData.csv",
    "table_name": "memberdata",
    "update_schema": true
  }'

# Check status
curl "http://localhost:8000/ingest/status/{job_id}"
```

---

### **Workflow 4: Query via Orchestration**

#### **Member Verification**:
```bash
curl -X POST "http://localhost:8000/orchestrate/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Is member M1001 active?"
  }'
```

#### **Deductible Lookup**:
```bash
curl -X POST "http://localhost:8000/orchestrate/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the deductible for member M1001?"
  }'
```

#### **Benefit Usage**:
```bash
curl -X POST "http://localhost:8000/orchestrate/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How many massage visits has member M1001 used?"
  }'
```

#### **Coverage Questions**:
```bash
curl -X POST "http://localhost:8000/orchestrate/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Is acupuncture covered?"
  }'
```

---

### **Workflow 5: RAG Pipeline Setup**

#### **Step 1: Prepare RAG Index**
```bash
curl -X POST "http://localhost:8000/rag/prepare" \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "mb-assistant-bucket",
    "textract_prefix": "mba/textract-output/",
    "index_name": "benefit_coverage_rag_index",
    "chunk_size": 1000,
    "chunk_overlap": 200
  }'
```

#### **Step 2: Query RAG**
```bash
curl -X POST "http://localhost:8000/rag/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the coverage limits for massage therapy?",
    "index_name": "benefit_coverage_rag_index",
    "k": 5
  }'
```

---

## API Reference

See [API_ENDPOINTS.md](API_ENDPOINTS.md) for complete API documentation with 20 endpoints covering:

- Health Check (1)
- Upload Endpoints (2)
- CSV Ingestion (3)
- Member Verification (2)
- Financial Lookups (2)
- RAG Services (2)
- Intent Identification (3)
- Orchestration (5)

---

## Database Schema

### **Table: memberdata**

```sql
CREATE TABLE memberdata (
    member_id VARCHAR(50) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    address VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    enrollment_date DATE,
    status VARCHAR(20) DEFAULT 'Active',
    INDEX idx_dob (dob),
    INDEX idx_name (last_name, first_name)
);
```

### **Table: deductibles_oop (Transposed)**

```sql
CREATE TABLE deductibles_oop (
    Metric VARCHAR(100) PRIMARY KEY,
    M1001 INTEGER,
    M1002 INTEGER,
    M1003 INTEGER,
    -- ... one column per member
);

-- Sample rows:
-- Metric                          | M1001 | M1002 | M1003
-- --------------------------------|-------|-------|-------
-- Deductible IND PPO              | 2683  | 3000  | 2500
-- Deductible IND PPO met          | 1840  | 1500  | 2000
-- Deductible IND PPO Remaining    | 843   | 1500  | 500
-- OOP IND PPO                     | 1120  | 5000  | 6000
```

### **Table: benefit_accumulator (Transposed)**

```sql
CREATE TABLE benefit_accumulator (
    Metric VARCHAR(100) PRIMARY KEY,
    M1001 INTEGER,
    M1002 INTEGER,
    M1003 INTEGER,
    -- ... one column per member
);

-- Sample rows:
-- Metric                              | M1001 | M1002 | M1003
-- ------------------------------------|-------|-------|-------
-- Massage Therapy Used                | 4     | 8     | 0
-- Massage Therapy Limit               | 12    | 12    | 12
-- Massage Therapy Remaining           | 8     | 4     | 12
-- Chiropractic Used                   | 8     | 15    | 5
```

---

## Testing

### **Unit Tests**

```bash
# Run all tests
pytest tests/

# Run specific agent tests
pytest tests/verification_agent/
pytest tests/orchestration_agent/

# Run with coverage
pytest --cov=src/MBA tests/
```

### **Integration Tests**

```bash
# Test API endpoints
python tests/orchestration_agent/test_orchestration_api.py

# Interactive testing
python interactive_orchestration_test.py
```

### **Test Queries**

See [TEST_QUERIES.md](TEST_QUERIES.md) for 100+ test queries across all intents.

---

## Deployment

### **Option 1: AWS Lambda**

```bash
# Package for Lambda
pip install -t package -r requirements.txt
cd package
zip -r ../lambda_function.zip .
cd ..
zip -g lambda_function.zip src/MBA/lambda_handlers/mba_ingest_lambda.py

# Deploy
aws lambda update-function-code \
  --function-name MBA-Ingest-Function \
  --zip-file fileb://lambda_function.zip
```

### **Option 2: Docker**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env .

EXPOSE 8000

CMD ["uvicorn", "MBA.microservices.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t mba-api .
docker run -p 8000:8000 mba-api
```

### **Option 3: EC2/ECS**

See deployment guide in `docs/DEPLOYMENT.md`

---

## Troubleshooting

### **Issue: Services Not Initialized**

**Error**: `503 Service Unavailable`

**Solution**:
1. Check `.env` file exists
2. Verify AWS credentials
3. Check database connectivity
4. Restart services

### **Issue: Database Connection Failed**

**Error**: `DatabaseError: Connection refused`

**Solution**:
1. Verify RDS endpoint in `.env`
2. Check security group allows port 3306
3. Verify credentials
4. Test with `debug_rds_connection.py`

### **Issue: Bedrock Access Denied**

**Error**: `AccessDenied: User not authorized`

**Solution**:
1. Check AWS IAM permissions
2. Verify Bedrock model access
3. Confirm region supports Bedrock
4. Check model ID is correct

### **Issue: Orchestration Returns Empty Results**

**Error**: `Failed to parse agent response`

**Solution**:
1. Check logs for tool execution
2. Verify global cache workaround
3. Restart API server
4. See [RAG_ORCHESTRATION_FIX.md](RAG_ORCHESTRATION_FIX.md)

---

## Project Structure

```
MBA_CT/
├── src/MBA/
│   ├── agents/                          # AI Agents
│   │   ├── member_verification_agent/   # Member identity verification
│   │   ├── deductible_oop_agent/        # Deductible/OOP lookup
│   │   ├── benefit_accumulator_agent/   # Benefit usage tracking
│   │   ├── benefit_coverage_rag_agent/  # Coverage policy RAG
│   │   ├── local_rag_agent/             # Uploaded document RAG
│   │   ├── intent_identification_agent/ # Intent classification
│   │   └── orchestration_agent/         # Multi-agent orchestration
│   │
│   ├── core/                            # Core utilities
│   │   ├── exceptions.py                # Custom exceptions
│   │   ├── logging_config.py            # Logging configuration
│   │   └── settings.py                  # Environment settings
│   │
│   ├── services/                        # Reusable services
│   │   ├── storage/                     # S3 and file handling
│   │   │   ├── s3_client.py
│   │   │   ├── file_processor.py
│   │   │   └── duplicate_detector.py
│   │   ├── ingestion/                   # CSV ingestion
│   │   │   ├── orchestrator.py
│   │   │   ├── loader.py
│   │   │   └── batch_processor.py
│   │   ├── database/                    # Database management
│   │   │   ├── client.py
│   │   │   ├── schema_manager.py
│   │   │   └── schema_inferrer.py
│   │   └── processing/                  # Document processing
│   │       ├── textract_client.py
│   │       └── audit_writer.py
│   │
│   ├── microservices/                   # API services
│   │   ├── api.py                       # FastAPI main application (20 endpoints)
│   │   └── s3_events.py                 # S3 event handlers
│   │
│   ├── ui/                              # Web interfaces
│   │   └── streamlit_app.py             # Streamlit UI (11 tabs)
│   │
│   ├── etl/                             # ETL utilities
│   │   ├── db.py                        # Database connector
│   │   └── __init__.py
│   │
│   └── lambda_handlers/                 # AWS Lambda functions
│       └── mba_ingest_lambda.py         # Ingestion Lambda
│
├── tests/                               # Test suite
│   ├── verification_agent/
│   ├── orchestration_agent/
│   └── intent_agent/
│
├── data/                                # Data directory
│   ├── csv/                             # CSV files for ingestion
│   └── uploads/                         # Temporary uploads
│
├── logs/                                # Application logs
│   └── app.log
│
├── docs/                                # Documentation
│   ├── API_ENDPOINTS.md                 # API reference
│   ├── TEST_QUERIES.md                  # Test queries
│   ├── TESTING_GUIDE.md                 # Testing guide
│   └── ORCHESTRATION_FIX.md             # Fix documentation
│
├── .env                                 # Environment variables (gitignored)
├── .gitignore                           # Git ignore rules
├── pyproject.toml                       # Project configuration
├── requirements.txt                     # Python dependencies
└── README.md                            # This file
```

---

## Development Guide

### **Code Standards**

- **Style**: PEP 8
- **Formatter**: Black
- **Linter**: Ruff
- **Type Hints**: Required for public APIs
- **Docstrings**: Google style

### **Adding a New Agent**

1. Create agent directory: `src/MBA/agents/new_agent/`
2. Create files:
   - `__init__.py` - Package exports
   - `agent.py` - Strands agent initialization
   - `tools.py` - @tool decorated functions
   - `prompt.py` - System prompt
   - `wrapper.py` - High-level interface
   - `README.md` - Documentation
3. Register in `src/MBA/agents/__init__.py`
4. Add to orchestration routing in `orchestration_agent/tools.py`
5. Create API endpoints in `microservices/api.py`
6. Add UI tab in `ui/streamlit_app.py`

### **Git Workflow**

```bash
# Create feature branch
git checkout -b feature/new-agent

# Make changes
git add .
git commit -m "Add new agent for X functionality"

# Push and create PR
git push origin feature/new-agent
```

---

## License

Copyright © 2025 MBA System. All rights reserved.

---

## Support & Documentation

- **API Reference**: [API_ENDPOINTS.md](API_ENDPOINTS.md)
- **Test Queries**: [TEST_QUERIES.md](TEST_QUERIES.md)
- **Testing Guide**: [TESTING_GUIDE.md](TESTING_GUIDE.md)
- **Agent READMEs**: [src/MBA/agents/](src/MBA/agents/)
- **Troubleshooting**: [RAG_ORCHESTRATION_FIX.md](RAG_ORCHESTRATION_FIX.md)

---

## Quick Start Checklist

- [ ] Clone repository
- [ ] Install Python 3.11+
- [ ] Install UV package manager
- [ ] Run `uv pip install -e .`
- [ ] Create `.env` file with AWS credentials
- [ ] Configure RDS connection
- [ ] Start FastAPI: `uv run mba-api`
- [ ] Start Streamlit: `uv run mba-app`
- [ ] Test health: `curl http://localhost:8000/health`
- [ ] Test orchestration: `curl -X POST http://localhost:8000/orchestrate/query -H "Content-Type: application/json" -d '{"query": "Is member M1001 active?"}'`

---

**Last Updated**: October 15, 2025
**Version**: 2.0.0
**Status**: Production Ready 🚀
