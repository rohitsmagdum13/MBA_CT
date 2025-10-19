# Benefit Coverage RAG Agent

## Overview

The Benefit Coverage RAG (Retrieval-Augmented Generation) Agent provides intelligent question answering over benefit coverage policy documents using AWS Bedrock and vector search.

**Key Features:**
- Extracts text from Textract-processed PDFs in S3
- Applies semantic-aware chunking for policy documents
- Creates searchable vector indexes with AWS Bedrock Titan Embeddings
- Answers policy questions using Claude LLM with source citations
- Reranks results using AWS Bedrock Cohere Rerank

---

## Architecture

```
┌─────────────┐
│   User PDF  │
└──────┬──────┘
       │ Upload to S3
       ▼
┌─────────────────────────────────┐
│  S3: mba/pdf/policy.pdf         │
└────────────┬────────────────────┘
             │ Trigger Textract Lambda
             ▼
┌─────────────────────────────────┐
│  AWS Textract Processing        │
│  - Text Extraction              │
│  - Table Detection              │
│  - Form Recognition             │
└────────────┬────────────────────┘
             │ Outputs JSON
             ▼
┌───────────────────────────────────────────┐
│  S3: mba/textract-output/                 │
│     mba/pdf/policy.pdf/job-123/           │
│         ├── manifest.json                 │
│         ├── page_0001.json                │
│         ├── page_0002.json                │
│         └── ...                            │
└───────────┬───────────────────────────────┘
            │
            │ 1. RAG Preparation
            ▼
┌───────────────────────────────────────────┐
│  Benefit Coverage RAG Agent               │
│  (prepare_rag_pipeline tool)              │
│                                            │
│  Step 1: Extract Text                     │
│    - Read Textract JSON files             │
│    - Extract LINE blocks                  │
│    - Preserve table markers               │
│    - Collect metadata (page, source)      │
│                                            │
│  Step 2: Intelligent Chunking             │
│    - Detect policy structure              │
│    - Preserve tables as atomic units      │
│    - Adaptive chunk sizes:                │
│      * 600 chars for tables/CPT codes     │
│      * 1000 chars for normal text         │
│      * 1500 chars for sparse content      │
│    - Extract metadata:                    │
│      * section_title                      │
│      * benefit_category                   │
│      * coverage_type                      │
│      * cpt_codes                          │
│      * has_cost_info                      │
│                                            │
│  Step 3: Generate Embeddings              │
│    - AWS Bedrock Titan Embeddings v2      │
│    - Dimension: 1536                      │
│    - Batch processing                     │
│                                            │
│  Step 4: Index in Vector Store            │
│    - OpenSearch or Qdrant                 │
│    - Content-based document IDs           │
│    - Metadata-enriched documents          │
└───────────┬───────────────────────────────┘
            │
            │ 2. Query Flow
            ▼
┌───────────────────────────────────────────┐
│  User Question                             │
│  "Is massage therapy covered?"            │
└───────────┬───────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────┐
│  RAG Query Agent (query_rag tool)         │
│                                            │
│  Step 1: Query Embedding                  │
│    - Bedrock Titan Embeddings             │
│    - Same model as indexing               │
│                                            │
│  Step 2: Semantic Search                  │
│    - Vector similarity search             │
│    - Retrieve top-k documents (k=5)       │
│    - Metadata filters (optional)          │
│                                            │
│  Step 3: Reranking                        │
│    - AWS Bedrock Cohere Rerank            │
│    - Relevance scoring                    │
│    - Top-n selection                      │
│                                            │
│  Step 4: Answer Generation                │
│    - AWS Bedrock Claude LLM               │
│    - Context-aware prompting              │
│    - Source attribution                   │
│    - Structured JSON response             │
└───────────┬───────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────┐
│  Response with Sources                     │
│  {                                         │
│    "answer": "Massage therapy is...",     │
│    "sources": [{...}, {...}]              │
│  }                                         │
└────────────────────────────────────────────┘
```

---

## Complete Data Flow

### 1. PDF Upload & Textract Processing

```bash
# Step 1: Upload PDF to S3
s3://mb-assistant-bucket/mba/pdf/policy.pdf

# Step 2: Textract Lambda processes the PDF (automatic trigger)
# Outputs stored at:
s3://mb-assistant-bucket/mba/textract-output/mba/pdf/policy.pdf/{job_id}/
    ├── manifest.json          # Job metadata
    ├── page_0001.json         # First page Textract output
    ├── page_0002.json         # Second page Textract output
    └── ...
```

**Textract Output Format (page_0001.json):**
```json
{
  "Blocks": [
    {
      "BlockType": "LINE",
      "Id": "block-1",
      "Text": "Therapy Services Coverage"
    },
    {
      "BlockType": "LINE",
      "Id": "block-2",
      "Text": "Massage therapy is covered with a limit of 6 visits per calendar year."
    },
    {
      "BlockType": "TABLE",
      "Id": "table-1",
      "Relationships": [...]
    }
  ]
}
```

### 2. RAG Pipeline Preparation

**API Endpoint:** `POST /rag/prepare`

**Request:**
```json
{
  "s3_bucket": "mb-assistant-bucket",
  "textract_prefix": "mba/textract-output/mba/pdf/policy.pdf/abc-123/",
  "index_name": "benefit_coverage_rag_index",
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

**Processing Steps:**

1. **Extract Text from Textract JSON:**
   ```python
   # Read all page_*.json files
   # Extract LINE blocks with text
   # Create Document objects with metadata

   Document(
       page_content="Massage therapy is covered...",
       metadata={
           "source": "page_0015.json",
           "page": 15,
           "s3_bucket": "mb-assistant-bucket",
           "s3_key": "mba/textract-output/.../page_0015.json",
           "has_tables": False
       }
   )
   ```

2. **Intelligent Chunking:**
   ```python
   # Detect content type
   is_table = detect_table(text)  # Check for pipes, CPT codes, columns

   # Adaptive chunk size
   if is_table or "CPT" in text:
       chunk_size = 600  # Smaller for dense content
   elif word_count < 20:
       chunk_size = 1500  # Larger for sparse content
   else:
       chunk_size = 1000  # Normal size

   # Extract metadata
   metadata = {
       "section_title": "Therapy Services",
       "benefit_category": "Therapy Services",
       "coverage_type": "covered",
       "cpt_codes": ["97110", "97112"],
       "has_cost_info": True,
       "page": 15
   }

   # Create chunk with enriched metadata
   Chunk(page_content=text, metadata=metadata)
   ```

3. **Generate Embeddings:**
   ```python
   # Call AWS Bedrock Titan Embeddings
   texts = [chunk.page_content for chunk in chunks]

   embeddings = get_bedrock_embeddings(texts)
   # Returns: List[List[float]] with dimension 1536
   ```

4. **Index in Vector Store:**
   ```python
   # Create content-based ID for deduplication
   content_hash = hashlib.sha256(chunk.page_content.encode()).hexdigest()
   doc_id = f"{content_hash}_{source}"

   # Index with metadata
   vector_store.index(
       id=doc_id,
       vector=embedding,
       text=chunk.page_content,
       metadata=chunk.metadata
   )
   ```

**Response:**
```json
{
  "success": true,
  "message": "Processed 10 docs into 45 chunks",
  "chunks_count": 45,
  "doc_count": 10,
  "index_name": "benefit_coverage_rag_index"
}
```

### 3. RAG Query Execution

**API Endpoint:** `POST /rag/query`

**Request:**
```json
{
  "question": "Is massage therapy covered?",
  "index_name": "benefit_coverage_rag_index",
  "k": 5
}
```

**Processing Steps:**

1. **Query Embedding:**
   ```python
   # Generate embedding for question
   query_embedding = get_bedrock_embeddings([question])[0]
   # Returns: List[float] with dimension 1536
   ```

2. **Semantic Search:**
   ```python
   # Vector similarity search
   results = vector_store.similarity_search(
       query_embedding=query_embedding,
       k=5,  # Retrieve top 5 documents
       filters={"benefit_category": "Therapy Services"}  # Optional
   )

   # Results contain:
   # - Document text
   # - Similarity score
   # - Metadata (page, section, etc.)
   ```

3. **Reranking:**
   ```python
   # Use AWS Bedrock Cohere Rerank
   doc_texts = [doc.page_content for doc in results]

   reranked_indices = rerank_documents(
       query=question,
       documents=doc_texts,
       top_n=3
   )

   # Returns indices in order of relevance: [2, 0, 4]
   reranked_docs = [results[i] for i in reranked_indices]
   ```

4. **Answer Generation:**
   ```python
   # Build context from top documents
   context = "\n\n".join([doc.page_content for doc in reranked_docs])

   # Call AWS Bedrock Claude
   answer = query_bedrock_llm(
       prompt=question,
       context=context,
       max_tokens=2000
   )

   # Returns structured answer based on retrieved context
   ```

**Response:**
```json
{
  "success": true,
  "answer": "Massage therapy is covered under your benefit plan with a limit of 6 visits per calendar year. This coverage falls under Therapy Services and does not require prior authorization. The copay is $20 for in-network PPO providers.",
  "sources": [
    {
      "source_id": 1,
      "content": "Massage Therapy: Covered benefit with 6 visit calendar year maximum. CPT Codes: 97124. Cost-sharing: $20 copay for PPO network.",
      "metadata": {
        "source": "page_0015.json",
        "page": 15,
        "section_title": "Therapy Services",
        "benefit_category": "Therapy Services",
        "coverage_type": "covered",
        "cpt_codes": ["97124"]
      }
    },
    {
      "source_id": 2,
      "content": "Therapy services do not require prior authorization for the first 6 visits per calendar year.",
      "metadata": {
        "source": "page_0018.json",
        "page": 18,
        "section_title": "Prior Authorization Requirements"
      }
    }
  ],
  "question": "Is massage therapy covered?",
  "retrieved_docs_count": 2
}
```

---

## Usage Examples

### Example 1: Prepare Pipeline from Textract Output

```bash
curl -X POST "http://localhost:8000/rag/prepare" \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "mb-assistant-bucket",
    "textract_prefix": "mba/textract-output/mba/pdf/benefits_2024.pdf/job-abc123/",
    "chunk_size": 1000,
    "chunk_overlap": 200
  }'
```

### Example 2: Query Benefit Coverage

```bash
curl -X POST "http://localhost:8000/rag/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the copay for physical therapy?",
    "k": 5
  }'
```

### Example 3: Python Integration

```python
from MBA.agents import BenefitCoverageRAGAgent

# Initialize agent
rag_agent = BenefitCoverageRAGAgent()

# Prepare pipeline
result = await rag_agent.prepare_pipeline(
    s3_bucket="mb-assistant-bucket",
    textract_prefix="mba/textract-output/mba/pdf/policy.pdf/job-123/"
)
print(f"Indexed {result['chunks_count']} chunks")

# Query documents
result = await rag_agent.query(
    question="Is massage therapy covered?"
)
print(result['answer'])
print(f"Sources: {len(result['sources'])}")
```

---

## Configuration

### Environment Variables

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# S3 Configuration
S3_BUCKET=mb-assistant-bucket
PDF_PREFIX=mba/pdf/
OUTPUT_PREFIX=mba/textract-output/

# Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0

# RAG Configuration
OPENSEARCH_ENDPOINT=your-opensearch-endpoint
OPENSEARCH_INDEX=benefit_coverage_rag_index
VECTOR_FIELD=vector_field
EMBEDDING_DIMENSION=1536

# Chunking Configuration
BULK_BATCH_SIZE=64
MAX_RETRIES=3
```

---

## Key Components

### 1. Document Class
Simple document representation compatible with LangChain:
```python
class Document:
    def __init__(self, page_content: str, metadata: Optional[Dict] = None):
        self.page_content = page_content
        self.metadata = metadata or {}
```

### 2. Intelligent Chunking Functions

- **`detect_table(text)`**: Identifies tabular content
- **`extract_metadata_enrichment(text)`**: Extracts policy-specific metadata
- **`chunk_documents(documents, chunk_size, chunk_overlap)`**: Creates optimized chunks

### 3. Embedding Functions

- **`get_bedrock_embeddings(texts)`**: Batch embedding generation
- **`query_bedrock_llm(prompt, context)`**: Answer generation
- **`rerank_documents(query, documents)`**: Relevance reranking

### 4. Tools

- **`prepare_rag_pipeline`**: End-to-end pipeline preparation
- **`query_rag`**: Question answering with sources

---

## Metadata Enrichment

Each chunk is enriched with benefit coverage-specific metadata:

| Metadata Field | Description | Example |
|----------------|-------------|---------|
| `section_title` | Policy section name | "Therapy Services" |
| `benefit_category` | Type of benefit | "Therapy Services", "Diagnostic Services" |
| `coverage_type` | Coverage status | "covered", "excluded", "prior_auth_required" |
| `cpt_codes` | Relevant CPT codes | ["97110", "97112", "97116"] |
| `has_cost_info` | Contains cost information | true/false |
| `source_page` | Original page number | 15 |
| `s3_key` | Source S3 path | "mba/textract-output/.../page_0015.json" |

---

## Error Handling

### Common Issues and Solutions

**1. Textract JSON Not Found:**
```json
{
  "success": false,
  "error": "No page JSON files found in Textract output"
}
```
**Solution:** Verify the textract_prefix path contains `page_*.json` files.

**2. Empty Text Extraction:**
```json
{
  "success": false,
  "error": "No text extracted from Textract JSON files"
}
```
**Solution:** Check that Textract successfully processed the PDF.

**3. Embedding Failure:**
```json
{
  "success": false,
  "error": "Failed to get embedding for text"
}
```
**Solution:** Verify AWS Bedrock credentials and model access.

---

## Performance Considerations

- **Chunk Size:** 1000 chars balances context and precision
- **Chunk Overlap:** 200 chars preserves cross-boundary context
- **Batch Size:** 64 chunks per bulk index operation
- **Embedding Model:** Titan v2 (1536 dimensions) for semantic quality
- **Reranking:** Cohere improves relevance by ~20-30%
- **LLM:** Claude Sonnet 4.5 for accurate, policy-compliant answers

---

## NEW: Dynamic File Upload + Auto RAG Pipeline

The Benefit Coverage RAG Agent now supports **dynamic document processing** with the new `/rag/upload-and-prepare` endpoint!

### How It Works

**Traditional Workflow (Manual):**
1. Upload PDF to S3
2. Wait for Textract Lambda to process
3. Manually call `/rag/prepare` with Textract output path
4. Query with `/rag/query`

**NEW Dynamic Workflow (Automatic):**
1. Upload PDF via `/rag/upload-and-prepare`
2. System automatically:
   - Uploads PDF to S3
   - Detects Textract output location
   - Runs RAG preparation pipeline
   - Indexes document for querying
3. Document ready for immediate querying!

### Usage Example

```bash
# Upload PDF and prepare RAG pipeline in one request
curl -X POST "http://localhost:8000/rag/upload-and-prepare" \
  -H "accept: application/json" \
  -F "file=@benefits_2024.pdf" \
  -F "index_name=benefits_2024_index" \
  -F "chunk_size=1000" \
  -F "chunk_overlap=200"

# Response
{
  "success": true,
  "message": "PDF uploaded and RAG pipeline prepared successfully",
  "file_name": "benefits_2024.pdf",
  "s3_uri": "s3://mb-assistant-bucket/mba/pdf/benefits_2024.pdf",
  "textract_output_prefix": "mba/textract-output/mba/pdf/benefits_2024.pdf/",
  "rag_preparation": {
    "success": true,
    "message": "Processed 15 docs into 67 chunks",
    "chunks_count": 67,
    "doc_count": 15,
    "index_name": "benefits_2024_index"
  },
  "query_ready": true,
  "next_steps": "You can now query this document using POST /rag/query with index_name='benefits_2024_index'"
}

# Immediately query the document
curl -X POST "http://localhost:8000/rag/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is covered under massage therapy?",
    "index_name": "benefits_2024_index",
    "k": 5
  }'
```

## Comprehensive Logging

The RAG pipeline now includes **detailed, easy-to-understand logs** at every step:

### 1. Textract Text Extraction Logs
```
================================================================================
STEP: EXTRACTING TEXT FROM TEXTRACT S3 OUTPUT
================================================================================
📦 S3 Bucket: mb-assistant-bucket
📁 Textract Prefix: mba/textract-output/mba/pdf/policy.pdf/
🌐 Full S3 Path: s3://mb-assistant-bucket/mba/textract-output/...

🔍 Listing objects in S3...
📂 Total files found in prefix: 16
   - manifest.json
   - page_0001.json
   - page_0002.json
   ...

✅ Found 15 Textract page JSON files

────────────────────────────────────────────────────────────
Processing Page 1/15: page_0001.json
   📥 Downloading from S3...
   📖 Page number: 1
   🔍 Total Textract blocks: 156
   📝 Extracted LINE blocks: 142
   📊 Detected TABLE blocks: 3
   📏 Total text length: 2,847 characters
   📄 Text preview: Therapy Services Coverage...
   ✅ Document created with 3 table markers

================================================================================
✅ TEXT EXTRACTION COMPLETE
📊 Summary:
   - Total pages processed: 15
   - Documents created: 15
   - Pages with tables: 8
   - Total characters extracted: 45,231
================================================================================
```

### 2. Intelligent Chunking Logs
```
================================================================================
STEP: INTELLIGENT DOCUMENT CHUNKING
================================================================================
📚 Documents to chunk: 15
📏 Default chunk size: 1000 characters
🔄 Chunk overlap: 200 characters

💡 Chunking Strategy:
   - Tables/CPT codes: 600 chars (smaller for dense content)
   - Sparse content (<20 words): 1500 chars (larger chunks)
   - Normal text: 1000 chars
   - Preserve paragraph boundaries
   - Extract metadata (section, category, CPT codes, etc.)

────────────────────────────────────────────────────────────
Processing Document 1/15
   📄 Source: page_0001.json
   📖 Page: 1
   📏 Length: 2847 characters
   📝 Paragraphs detected: 12

   Para 1: Type=NORMAL, Size=456 chars, Words=67
      Adaptive chunk size: 1000
      Preview: Therapy Services Coverage\n\nMassage Therapy is a covered benefit...

   ✅ Chunk 1 created:
      Length: 987 chars
      Metadata: {'benefit_category': 'Therapy Services', 'cpt_codes': ['97124']}
      Content: Massage Therapy is a covered benefit...

   ✅ Document 1 produced 3 chunks

================================================================================
✅ CHUNKING COMPLETE
📊 Summary:
   - Total documents processed: 15
   - Total chunks created: 67
   - Average chunks per document: 4.5
   - Min chunk size: 456 chars
   - Max chunk size: 1498 chars
   - Average chunk size: 892 chars
   - Chunks with CPT codes: 23
   - Chunks with benefit category: 45
================================================================================
```

### 3. Embedding Generation Logs
```
================================================================================
STEP: GENERATING EMBEDDINGS WITH AWS BEDROCK TITAN
================================================================================
📊 Total texts to embed: 67
🤖 Model: amazon.titan-embed-text-v2:0
📐 Output dimension: 1024

🔄 Processing text 1/67
   📝 Text length: 987 characters
   📄 Preview: Massage Therapy is a covered benefit...
   🌐 Calling Bedrock Titan API...
   ✅ Embedding generated successfully
   📊 Vector dimension: 1024
   🔢 Vector sample (first 5 values): [0.0234, -0.0156, 0.0892, ...]

...

✅ EMBEDDING GENERATION COMPLETE
📊 Successfully generated: 67/67 embeddings
⚠️  Fallback vectors used: 0/67
================================================================================
```

### 4. Vector Indexing Logs
```
================================================================================
STEP: INDEXING IN QDRANT VECTOR STORE
================================================================================
🗄️  Qdrant URL: http://localhost:6333
📁 Collection name: benefit_coverage_rag_index
📐 Vector dimension: 1024
📏 Distance metric: COSINE

🔌 Connecting to Qdrant...
✅ Connected to Qdrant successfully

🔍 Checking if collection 'benefit_coverage_rag_index' exists...
📚 Existing collections: ['benefit_coverage_rag_index', 'test_collection']
✅ Collection 'benefit_coverage_rag_index' already exists, will upsert points

🔨 Building vector points for indexing...

   Point 1:
      ID: f7e8a9b2-4c3d-1e5f-6a7b-8c9d0e1f2a3b
      Vector dimension: 1024
      Vector sample: [0.0234, -0.0156, 0.0892]
      Payload keys: ['source', 'page', 's3_bucket', 'benefit_category', 'cpt_codes']
      Text preview: Massage Therapy is a covered benefit...

✅ Built 67 vector points

📤 Upserting 67 points to Qdrant collection 'benefit_coverage_rag_index'...

✅ INDEXING COMPLETE
📊 Successfully indexed 67 chunks into Qdrant collection 'benefit_coverage_rag_index'
📈 Collection info:
   - Total vectors: 67
   - Vector dimension: 1024
   - Distance metric: Cosine
================================================================================
```

### 5. Query Embedding & Search Logs
```
================================================================================
STEP 1: GENERATING QUERY EMBEDDING
================================================================================
🔍 Query: Is massage therapy covered?
📏 Query length: 29 characters
...
✅ Query embedding generated
📐 Embedding dimension: 1024

================================================================================
STEP 2: SEMANTIC SEARCH IN VECTOR STORE
================================================================================
🗄️  Qdrant URL: http://localhost:6333
📁 Collection: benefit_coverage_rag_index
🎯 Retrieving top k=5 documents

🔌 Connecting to Qdrant...
✅ Connected successfully

🔍 Performing vector similarity search...
✅ Search complete, found 5 results

📄 Retrieved documents:

   Result 1:
      Score: 0.8734
      Source: page_0001.json
      Page: 1
      Text length: 987 chars
      Preview: Massage Therapy is a covered benefit...

   Result 2:
      Score: 0.7821
      Source: page_0002.json
      Page: 2
      Text length: 756 chars
      Preview: Therapy Services cost-sharing...

✅ Retrieved 5 documents from Qdrant
================================================================================
```

### 6. Reranking Logs
```
================================================================================
STEP: RERANKING DOCUMENTS WITH AWS BEDROCK COHERE
================================================================================
🔍 Query: Is massage therapy covered?
📚 Documents to rerank: 5
🎯 Top N to return: 5
🤖 Model: cohere.rerank-v3-5:0

📄 Document previews before reranking:
   Doc 0: Massage Therapy is a covered benefit...
   Doc 1: Therapy Services cost-sharing...
   Doc 2: Prior authorization requirements...
   Doc 3: Excluded services and limitations...
   Doc 4: Appeal process for denied claims...

🌐 Calling Bedrock Cohere Rerank API...

✅ RERANKING COMPLETE
📊 Reranking results:
   Rank 1: Original Index 0, Score 0.9876
      └─ Massage Therapy is a covered benefit...
   Rank 2: Original Index 1, Score 0.8234
      └─ Therapy Services cost-sharing...
   Rank 3: Original Index 2, Score 0.5612
      └─ Prior authorization requirements...

🎯 Final reranked indices: [0, 1, 2, 3, 4]
================================================================================
```

### Logging Benefits

1. **Troubleshooting**: Easily identify where RAG pipeline fails
2. **Performance Monitoring**: Track processing times and bottlenecks
3. **Data Validation**: Verify text extraction, chunking, and embedding quality
4. **Transparency**: Understand exactly how documents are processed and indexed
5. **Debugging**: Detailed context for error resolution

## Future Enhancements

1. **Vector Store Options:** Support for Pinecone, Weaviate
2. **Hybrid Search:** Combine vector similarity with keyword search
3. **Multi-Document Queries:** Cross-reference multiple policy documents
4. **Conversation Memory:** Multi-turn question answering
5. **Query Analytics:** Track common questions and answer quality
6. **Textract Webhook Integration:** Real-time notification when Textract completes

---

## Testing

```bash
# Test RAG preparation
pytest tests/agents/test_benefit_coverage_rag_agent.py::test_prepare_pipeline

# Test RAG query
pytest tests/agents/test_benefit_coverage_rag_agent.py::test_query_rag

# Integration test
pytest tests/integration/test_rag_end_to_end.py
```

---

## Support

For issues or questions:
- Check logs: `src/MBA/agents/benefit_coverage_rag_agent/`
- Review Textract output: `s3://{bucket}/mba/textract-output/`
- Verify embeddings: Test with sample query
- Contact: MBA development team
