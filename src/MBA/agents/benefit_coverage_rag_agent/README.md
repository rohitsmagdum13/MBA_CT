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

## Future Enhancements

1. **Vector Store Options:** Support for Pinecone, Weaviate
2. **Hybrid Search:** Combine vector similarity with keyword search
3. **Multi-Document Queries:** Cross-reference multiple policy documents
4. **Conversation Memory:** Multi-turn question answering
5. **Query Analytics:** Track common questions and answer quality
6. **Automated Pipeline:** Trigger RAG prep on Textract completion

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
