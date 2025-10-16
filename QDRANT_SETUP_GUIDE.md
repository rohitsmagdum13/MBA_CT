# Qdrant Vector Store Setup Guide for MBA RAG System

Complete guide to configure Qdrant for benefit coverage document indexing and retrieval.

---

## Table of Contents

1. [What is Qdrant](#what-is-qdrant)
2. [Setup Options](#setup-options)
3. [Installation & Configuration](#installation--configuration)
4. [Code Integration](#code-integration)
5. [Testing](#testing)
6. [Production Deployment](#production-deployment)

---

## What is Qdrant

**Qdrant** is a high-performance vector database optimized for:
- ✅ Fast semantic search
- ✅ Efficient similarity matching
- ✅ Metadata filtering
- ✅ Scalable to millions of vectors
- ✅ Easy to deploy (Docker, Cloud, Self-hosted)

**Why Qdrant for MBA System:**
- Simple Python API
- Excellent performance for medical document search
- Built-in filtering by metadata (page numbers, sections, etc.)
- Cost-effective (free tier available)

---

## Setup Options

### Option 1: Qdrant Cloud (Recommended for Production)
- ✅ Fully managed
- ✅ Free tier: 1GB cluster
- ✅ No infrastructure management
- ✅ Automatic backups
- ⚠️ Requires internet connection

### Option 2: Docker (Recommended for Development)
- ✅ Easy local setup
- ✅ Full control
- ✅ No external dependencies
- ✅ Fast development cycle
- ⚠️ Requires Docker installed

### Option 3: Self-Hosted (Advanced)
- ✅ Complete control
- ✅ Can run on EC2/ECS
- ✅ Best for large-scale production
- ⚠️ More complex setup

---

## Installation & Configuration

### Step 1: Install Qdrant Client

```bash
# Activate your environment
conda activate MBA_CT

# Install Qdrant Python client
pip install qdrant-client

# Verify installation
python -c "from qdrant_client import QdrantClient; print('Qdrant client installed!')"
```

---

### Step 2A: Setup Qdrant Cloud (Production)

#### 2A.1: Create Qdrant Cloud Account

1. **Go to:** https://cloud.qdrant.io/
2. **Sign up** with email or GitHub
3. **Create a cluster:**
   - Cluster name: `mba-rag-production`
   - Region: Choose closest to your AWS region (e.g., `us-east-1`)
   - Tier: Start with **Free** (1GB)
4. **Get credentials:**
   - Click on your cluster
   - Copy **API URL** (e.g., `https://xyz-123.us-east.aws.cloud.qdrant.io:6333`)
   - Copy **API Key** (in "API Keys" tab)

#### 2A.2: Update `.env` File

Add to your `.env`:

```bash
# Qdrant Configuration
QDRANT_HOST=https://xyz-123.us-east.aws.cloud.qdrant.io
QDRANT_PORT=6333
QDRANT_API_KEY=your-api-key-here
QDRANT_COLLECTION_NAME=benefit_coverage_rag
QDRANT_USE_GRPC=false
```

---

### Step 2B: Setup Qdrant with Docker (Development)

#### 2B.1: Start Qdrant Container

```bash
# Pull and run Qdrant
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest

# Verify it's running
docker ps | grep qdrant

# Check logs
docker logs qdrant
```

#### 2B.2: Update `.env` File

Add to your `.env`:

```bash
# Qdrant Configuration (Local Docker)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=  # Leave empty for local Docker
QDRANT_COLLECTION_NAME=benefit_coverage_rag
QDRANT_USE_GRPC=false
```

#### 2B.3: Verify Qdrant is Running

```bash
# Test API endpoint
curl http://localhost:6333/

# Expected output:
# {"title":"qdrant - vector search engine","version":"1.x.x"}
```

Or open in browser: http://localhost:6333/dashboard

---

### Step 3: Update MBA Configuration

#### 3.1: Update `.env` File (Complete)

```bash
# AWS Configuration
AWS_DEFAULT_REGION=us-east-1

# Bedrock Model IDs
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0

# Bedrock Configuration
EMBEDDING_DIMENSION=1024  # Titan v2 uses 1024 dimensions

# Qdrant Vector Store Configuration
QDRANT_HOST=localhost  # Or your cloud URL
QDRANT_PORT=6333
QDRANT_API_KEY=  # Your API key (if using cloud)
QDRANT_COLLECTION_NAME=benefit_coverage_rag
QDRANT_USE_GRPC=false

# S3 Configuration
S3_BUCKET_NAME=your-mba-bucket-name
```

#### 3.2: Update `settings.py`

Add Qdrant configuration to your settings:

**File:** `src/MBA/core/settings.py`

```python
class Settings:
    # ... existing settings ...

    # Qdrant Vector Store Settings
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    qdrant_collection_name: str = os.getenv("QDRANT_COLLECTION_NAME", "benefit_coverage_rag")
    qdrant_use_grpc: bool = os.getenv("QDRANT_USE_GRPC", "false").lower() == "true"
```

---

## Code Integration

### Step 4: Update `tools.py` with Qdrant Integration

I'll create the complete Qdrant integration for your RAG pipeline:

**File:** `src/MBA/agents/benefit_coverage_rag_agent/tools.py`

#### 4.1: Add Qdrant Imports

```python
# Add to existing imports at top of file
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)
```

#### 4.2: Initialize Qdrant Client

```python
# Add after bedrock_runtime initialization (around line 60)

# Initialize Qdrant client
def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client with proper configuration."""
    if settings.qdrant_api_key:
        # Cloud deployment
        logger.info(f"Connecting to Qdrant Cloud at {settings.qdrant_host}")
        return QdrantClient(
            url=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
            prefer_grpc=settings.qdrant_use_grpc
        )
    else:
        # Local deployment
        logger.info(f"Connecting to local Qdrant at {settings.qdrant_host}:{settings.qdrant_port}")
        return QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            prefer_grpc=settings.qdrant_use_grpc
        )

qdrant_client = get_qdrant_client()
```

#### 4.3: Create Collection Helper Function

```python
# Add after qdrant_client initialization

def ensure_qdrant_collection_exists(collection_name: str, dimension: int = EMBEDDING_DIMENSION):
    """
    Ensure Qdrant collection exists with proper configuration.

    Args:
        collection_name: Name of the collection
        dimension: Embedding vector dimension (1024 for Titan v2)
    """
    try:
        # Check if collection exists
        collections = qdrant_client.get_collections().collections
        collection_names = [col.name for col in collections]

        if collection_name in collection_names:
            logger.info(f"Qdrant collection '{collection_name}' already exists")

            # Verify dimension matches
            collection_info = qdrant_client.get_collection(collection_name)
            existing_dim = collection_info.config.params.vectors.size

            if existing_dim != dimension:
                logger.warning(
                    f"Collection '{collection_name}' has dimension {existing_dim}, "
                    f"but expected {dimension}. Consider recreating the collection."
                )
            return

        # Create new collection
        logger.info(f"Creating Qdrant collection '{collection_name}' with dimension {dimension}")

        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE  # Use cosine similarity for semantic search
            )
        )

        logger.info(f"Successfully created collection '{collection_name}'")

    except Exception as e:
        logger.error(f"Failed to ensure Qdrant collection exists: {str(e)}")
        raise
```

#### 4.4: Update `prepare_rag_pipeline` Tool

Replace the stub implementation (lines 496-500) with actual Qdrant indexing:

```python
        # Step 4: Index in Qdrant vector store
        collection_name = index_name or settings.qdrant_collection_name

        # Ensure collection exists
        ensure_qdrant_collection_exists(collection_name, EMBEDDING_DIMENSION)

        # Prepare points for Qdrant
        points = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point = PointStruct(
                id=idx,  # Qdrant will auto-generate UUID if needed
                vector=embedding,
                payload={
                    "text": chunk.page_content,
                    "source": chunk.metadata.get("source", "unknown"),
                    "page": chunk.metadata.get("page", 0),
                    "s3_bucket": chunk.metadata.get("s3_bucket", ""),
                    "s3_key": chunk.metadata.get("s3_key", ""),
                    "has_tables": chunk.metadata.get("has_tables", False),
                    "section_title": chunk.metadata.get("section_title", ""),
                    "benefit_category": chunk.metadata.get("benefit_category", ""),
                    "coverage_type": chunk.metadata.get("coverage_type", ""),
                    "cpt_codes": chunk.metadata.get("cpt_codes", []),
                    "has_cost_info": chunk.metadata.get("has_cost_info", False),
                }
            )
            points.append(point)

        # Upload to Qdrant in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            qdrant_client.upsert(
                collection_name=collection_name,
                points=batch,
                wait=True  # Wait for operation to complete
            )
            logger.info(f"Uploaded batch {i // batch_size + 1}/{(len(points) + batch_size - 1) // batch_size}")

        logger.info(f"Successfully indexed {len(points)} chunks in Qdrant collection '{collection_name}'")
```

#### 4.5: Update `query_rag` Tool

Replace the stub implementation (lines 562-576) with actual Qdrant search:

```python
        # Step 2: Search vector store (Qdrant)
        collection_name = index_name or settings.qdrant_collection_name

        # Perform similarity search
        search_results = qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=k * 2,  # Get extra results for reranking
            with_payload=True,
            with_vectors=False  # Don't need vectors back
        )

        # Convert to Document objects
        retrieved_docs = []
        for result in search_results:
            doc = Document(
                page_content=result.payload.get("text", ""),
                metadata={
                    "source": result.payload.get("source", ""),
                    "page": result.payload.get("page", 0),
                    "section_title": result.payload.get("section_title", ""),
                    "benefit_category": result.payload.get("benefit_category", ""),
                    "coverage_type": result.payload.get("coverage_type", ""),
                    "similarity_score": result.score
                }
            )
            retrieved_docs.append(doc)

        logger.info(f"Retrieved {len(retrieved_docs)} documents from Qdrant")
```

---

## Complete Updated `tools.py`

I'll create a file with all the Qdrant integration code ready to use:

**File:** `src/MBA/agents/benefit_coverage_rag_agent/tools.py`

Key changes:
1. Import Qdrant client and models
2. Initialize Qdrant client
3. Add collection creation helper
4. Update `prepare_rag_pipeline` to index in Qdrant
5. Update `query_rag` to search Qdrant

---

## Testing

### Test 1: Verify Qdrant Connection

Create `test_qdrant_connection.py`:

```python
from qdrant_client import QdrantClient
import os

# Load your config
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Connect to Qdrant
if QDRANT_API_KEY:
    client = QdrantClient(url=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY)
else:
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Test connection
try:
    collections = client.get_collections()
    print(f"✅ Connected to Qdrant!")
    print(f"   Existing collections: {[c.name for c in collections.collections]}")
except Exception as e:
    print(f"❌ Failed to connect: {e}")
```

Run:
```bash
python test_qdrant_connection.py
```

### Test 2: Test RAG Pipeline with Qdrant

```bash
# Start your FastAPI server
uvicorn main:app --reload

# Test prepare pipeline
curl -X POST http://localhost:8000/benefit-coverage-rag/prepare \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "your-bucket",
    "textract_prefix": "mba/textract-output/..."
  }'

# Test query
curl -X POST http://localhost:8000/benefit-coverage-rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Is massage therapy covered?"
  }'
```

---

## Production Deployment

### Option 1: Qdrant Cloud (Recommended)

**Pros:**
- ✅ Fully managed
- ✅ Automatic scaling
- ✅ Built-in backups
- ✅ High availability

**Pricing:**
- Free tier: 1GB cluster
- Paid: Starting at $25/month for 1GB RAM

**Setup:**
1. Create cluster at https://cloud.qdrant.io/
2. Copy API URL and key
3. Update Lambda environment variables
4. Deploy!

---

### Option 2: Self-Hosted on AWS EC2

**Pros:**
- ✅ Full control
- ✅ Can optimize costs
- ✅ Isolated network

**Setup:**

```bash
# Launch EC2 instance (t3.medium recommended)
# Install Docker
sudo yum install -y docker
sudo service docker start

# Run Qdrant
docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -p 6334:6334 \
  -v /data/qdrant:/qdrant/storage \
  qdrant/qdrant:latest

# Update security group to allow port 6333 from Lambda VPC
```

**Lambda Configuration:**
```bash
QDRANT_HOST=http://your-ec2-private-ip
QDRANT_PORT=6333
QDRANT_API_KEY=  # Optional: can set auth
```

---

### Option 3: Qdrant on AWS ECS/Fargate

**Pros:**
- ✅ Serverless container
- ✅ Auto-scaling
- ✅ Pay per use

**Setup:**
1. Create ECS cluster
2. Create task definition with Qdrant image
3. Deploy service
4. Use AWS Service Discovery for DNS

---

## Cost Comparison

| Option | Setup Time | Monthly Cost | Best For |
|--------|-----------|--------------|----------|
| **Qdrant Cloud (Free)** | 5 min | $0 | Development, small apps |
| **Qdrant Cloud (Paid)** | 5 min | $25-100+ | Production, medium scale |
| **EC2 t3.medium** | 30 min | $30 | Full control, custom config |
| **ECS Fargate** | 1 hour | $15-50 | Serverless, auto-scaling |
| **Local Docker** | 2 min | $0 | Development only |

---

## Qdrant vs OpenSearch

| Feature | Qdrant | OpenSearch |
|---------|--------|------------|
| **Setup** | ✅ Very easy | ⚠️ Complex |
| **Vector Search** | ✅ Optimized | ⚠️ Slower |
| **Cost** | ✅ Lower | ⚠️ Higher |
| **Python API** | ✅ Simple | ⚠️ Complex |
| **Filtering** | ✅ Excellent | ✅ Good |
| **Hybrid Search** | ✅ Yes | ✅ Yes |
| **Best For** | Vector-first apps | Text + vectors |

**Recommendation:** Use **Qdrant** for your MBA RAG system - it's simpler and more cost-effective.

---

## Troubleshooting

### Issue 1: "Connection refused"

**Cause:** Qdrant not running or wrong host/port

**Solution:**
```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Check logs
docker logs qdrant

# Restart if needed
docker restart qdrant
```

### Issue 2: "Dimension mismatch"

**Cause:** Existing collection has wrong dimension

**Solution:**
```python
# Delete and recreate collection
from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)
client.delete_collection("benefit_coverage_rag")

# Then re-run prepare_rag_pipeline
```

### Issue 3: "API key invalid"

**Cause:** Wrong or expired API key

**Solution:**
1. Go to Qdrant Cloud dashboard
2. Generate new API key
3. Update `.env` file
4. Restart your application

---

## Summary Checklist

### Setup:
- [ ] Install Qdrant (Docker or Cloud)
- [ ] Install `qdrant-client` Python package
- [ ] Update `.env` with Qdrant configuration
- [ ] Update `settings.py` with Qdrant settings

### Code Integration:
- [ ] Add Qdrant imports to `tools.py`
- [ ] Initialize Qdrant client
- [ ] Update `prepare_rag_pipeline` tool
- [ ] Update `query_rag` tool

### Testing:
- [ ] Test Qdrant connection
- [ ] Test document indexing
- [ ] Test similarity search
- [ ] Test end-to-end RAG query

### Production:
- [ ] Choose deployment option (Cloud/EC2/ECS)
- [ ] Configure security (API keys, network)
- [ ] Set up monitoring
- [ ] Configure backups

---

## Next Steps

1. **Choose deployment option** (Docker local for development)
2. **Install dependencies:** `pip install qdrant-client`
3. **Start Qdrant:** Use Docker command above
4. **Update code:** I'll create the updated `tools.py` for you
5. **Test:** Run prepare and query workflows

---

**Ready to implement? I can update your `tools.py` file with complete Qdrant integration now!**
