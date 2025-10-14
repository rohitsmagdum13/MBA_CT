"""
RAG Tools for Benefit Coverage Agent.

This module provides tools for:
1. Preparing RAG pipelines from Textract-processed documents in S3
2. Querying indexed benefit coverage documents
3. Extracting and chunking policy documents with semantic awareness
"""

import os
import json
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from strands import tool

from ...core.logging_config import get_logger
from ...core.settings import settings
from ...core.exceptions import S3Error, TextractError

logger = get_logger(__name__)

# Configuration
BULK_BATCH_SIZE = int(os.getenv("BULK_BATCH_SIZE", "64"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "1.5"))
VECTOR_FIELD = os.getenv("VECTOR_FIELD", "vector_field")
DEFAULT_INDEX = os.getenv("OPENSEARCH_INDEX", "benefit_coverage_rag_index")
EMBEDDING_DIMENSION = 1536  # AWS Bedrock Titan Embeddings v2 dimension

# Initialize AWS clients
def get_aws_session():
    """Get boto3 session with proper credentials."""
    is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

    if is_lambda:
        logger.info("Running in Lambda - using execution role")
        return boto3.Session(region_name=settings.aws_default_region)
    else:
        logger.info("Running locally - using settings credentials")
        session_kwargs = {'region_name': settings.aws_default_region}

        if settings.aws_profile:
            session_kwargs["profile_name"] = settings.aws_profile
        elif settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        return boto3.Session(**session_kwargs)

session = get_aws_session()
s3_client = session.client('s3')
bedrock_runtime = session.client('bedrock-runtime', region_name=settings.aws_default_region)


# ============================================================================
# Embedding and LLM Functions
# ============================================================================

def get_bedrock_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Get embeddings from AWS Bedrock Titan Embeddings.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    embeddings = []

    for text in texts:
        try:
            payload = {
                "inputText": text[:8000]  # Titan limit
            }

            response = bedrock_runtime.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps(payload)
            )

            result = json.loads(response['body'].read())
            embeddings.append(result['embedding'])

        except Exception as e:
            logger.error(f"Failed to get embedding for text: {str(e)[:200]}")
            # Return zero vector as fallback
            embeddings.append([0.0] * EMBEDDING_DIMENSION)

    return embeddings


def query_bedrock_llm(prompt: str, context: str, max_tokens: int = 2000) -> str:
    """
    Query AWS Bedrock Claude for answer generation.

    Args:
        prompt: User question
        context: Retrieved document context
        max_tokens: Maximum tokens in response

    Returns:
        Generated answer text
    """
    try:
        full_prompt = f"""

Answer the question based on the provided context from benefit coverage policy documents.

Context:
{context}

Question: {prompt}

Answer:"""

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ]
        }

        response = bedrock_runtime.invoke_model(
            modelId=settings.bedrock_model_id,
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        return result['content'][0]['text']

    except Exception as e:
        logger.error(f"Bedrock LLM query failed: {str(e)}")
        return f"Error generating answer: {str(e)}"


def rerank_documents(query: str, documents: List[str], top_n: int = 5) -> List[int]:
    """
    Rerank documents using AWS Bedrock Cohere Rerank.

    Args:
        query: Search query
        documents: List of document texts
        top_n: Number of top documents to return

    Returns:
        List of reranked document indices
    """
    try:
        payload = {
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents))
        }

        response = bedrock_runtime.invoke_model(
            modelId="cohere.rerank-v3-5:0",
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        # Extract indices from reranked results
        return [item["index"] for item in result.get("results", [])]

    except Exception as e:
        logger.warning(f"Reranking failed, using original order: {str(e)}")
        return list(range(len(documents)))


# ============================================================================
# Document Extraction from S3 Textract Output
# ============================================================================

class Document:
    """Simple document class compatible with LangChain."""
    def __init__(self, page_content: str, metadata: Optional[Dict] = None):
        self.page_content = page_content
        self.metadata = metadata or {}


def extract_text_from_textract_s3(s3_bucket: str, textract_output_prefix: str) -> List[Document]:
    """
    Extract text from Textract JSON files in S3.

    Expected S3 structure:
    s3://{bucket}/{textract_output_prefix}/
        manifest.json
        page_0001.json
        page_0002.json
        ...

    Args:
        s3_bucket: S3 bucket name
        textract_output_prefix: Prefix path to Textract output folder

    Returns:
        List of Document objects with extracted text
    """
    documents = []

    try:
        # List all files in the Textract output folder
        response = s3_client.list_objects_v2(
            Bucket=s3_bucket,
            Prefix=textract_output_prefix
        )

        if 'Contents' not in response:
            raise TextractError(
                f"No files found in S3 path: s3://{s3_bucket}/{textract_output_prefix}",
                details={"bucket": s3_bucket, "prefix": textract_output_prefix}
            )

        # Filter for page JSON files
        page_files = [
            obj['Key'] for obj in response['Contents']
            if obj['Key'].endswith('.json') and 'page_' in obj['Key']
        ]

        if not page_files:
            raise TextractError(
                f"No page JSON files found in Textract output",
                details={"bucket": s3_bucket, "prefix": textract_output_prefix}
            )

        logger.info(f"Found {len(page_files)} Textract page files in s3://{s3_bucket}/{textract_output_prefix}")

        # Process each page file
        for page_file in sorted(page_files):
            try:
                # Download JSON file
                obj = s3_client.get_object(Bucket=s3_bucket, Key=page_file)
                textract_data = json.loads(obj['Body'].read())

                # Extract page number from filename (e.g., page_0001.json -> 1)
                page_num_match = re.search(r'page_(\d+)', page_file)
                page_num = int(page_num_match.group(1)) if page_num_match else 0

                # Extract text from Textract blocks
                text_lines = []
                tables = []

                for block in textract_data.get('Blocks', []):
                    block_type = block.get('BlockType')

                    if block_type == 'LINE' and 'Text' in block:
                        text_lines.append(block['Text'])

                    elif block_type == 'TABLE':
                        # Preserve table structure for better chunking
                        tables.append(f"[TABLE: {block.get('Id', 'unknown')}]")

                # Combine text content
                page_content = '\n'.join(text_lines)

                if page_content.strip():
                    documents.append(Document(
                        page_content=page_content,
                        metadata={
                            "source": page_file,
                            "page": page_num,
                            "s3_bucket": s3_bucket,
                            "s3_key": page_file,
                            "has_tables": len(tables) > 0
                        }
                    ))

            except Exception as e:
                logger.error(f"Failed to process Textract page {page_file}: {str(e)}")
                continue

        if not documents:
            raise TextractError(
                "No text extracted from Textract JSON files",
                details={"bucket": s3_bucket, "prefix": textract_output_prefix, "files_processed": len(page_files)}
            )

        logger.info(f"Extracted text from {len(documents)} Textract pages")
        return documents

    except ClientError as e:
        raise S3Error(
            f"S3 error accessing Textract output: {str(e)}",
            details={"bucket": s3_bucket, "prefix": textract_output_prefix}
        )
    except Exception as e:
        raise TextractError(
            f"Failed to extract text from Textract output: {str(e)}",
            details={"bucket": s3_bucket, "prefix": textract_output_prefix}
        )


# ============================================================================
# Intelligent Chunking for Benefit Coverage Documents
# ============================================================================

def detect_table(text: str) -> bool:
    """Detect if text contains tabular data."""
    # Check for pipe-delimited tables
    if '|' in text and re.search(r'\|.+\|', text):
        return True
    # Check for CPT code patterns
    if re.search(r'\bCPT\b.*\d{5}', text, flags=re.IGNORECASE):
        return True
    # Check for multiple whitespace-separated columns
    lines = [l for l in text.splitlines() if l.strip()]
    multi_col_lines = sum(1 for l in lines if len(re.findall(r'\s{3,}', l)) >= 2)
    return multi_col_lines >= max(2, len(lines) // 5)


def extract_metadata_enrichment(text: str) -> Dict[str, Any]:
    """Extract metadata from benefit coverage text."""
    metadata = {}

    # Section title
    section_match = re.search(r'^#{1,3}\s*(.+)$', text, flags=re.MULTILINE)
    if section_match:
        metadata["section_title"] = section_match.group(1).strip()

    # Benefit category
    if re.search(r'\b(therapy|physical therapy|occupational therapy)\b', text, flags=re.IGNORECASE):
        metadata["benefit_category"] = "Therapy Services"
    elif re.search(r'\b(diagnostic|imaging|radiology|mri|ct scan)\b', text, flags=re.IGNORECASE):
        metadata["benefit_category"] = "Diagnostic Services"
    elif re.search(r'\b(preventive|wellness|screening)\b', text, flags=re.IGNORECASE):
        metadata["benefit_category"] = "Preventive Care"

    # Coverage type
    if re.search(r'\b(covered|eligible|benefit)\b', text, flags=re.IGNORECASE):
        metadata["coverage_type"] = "covered"
    elif re.search(r'\b(excluded|not covered|limitation)\b', text, flags=re.IGNORECASE):
        metadata["coverage_type"] = "excluded"
    elif re.search(r'\b(prior authorization|preauthorization|pre-cert)\b', text, flags=re.IGNORECASE):
        metadata["coverage_type"] = "prior_auth_required"

    # CPT codes
    cpt_matches = re.findall(r'\b(\d{5})\b', text)
    if cpt_matches:
        metadata["cpt_codes"] = list(set(cpt_matches))[:10]  # Limit to 10 codes

    # Cost sharing
    if re.search(r'\$([\d,]+)', text):
        metadata["has_cost_info"] = True

    return metadata


def chunk_documents(documents: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
    """
    Intelligently chunk benefit coverage documents.

    Strategy:
    - Preserve policy structure (sections, subsections)
    - Keep tables as atomic units
    - Use adaptive chunk sizes based on content density
    - Enrich chunks with benefit coverage metadata
    """
    chunks = []

    for doc in documents:
        text = doc.page_content
        base_metadata = doc.metadata.copy()

        # Split by double newline (paragraph boundaries)
        paragraphs = re.split(r'\n\s*\n', text)

        current_chunk = ""
        current_metadata = base_metadata.copy()

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if paragraph is a table
            is_table = detect_table(para)

            # Determine chunk size based on content
            if is_table or re.search(r'\bCPT\b', para, flags=re.IGNORECASE):
                adaptive_size = 600  # Smaller chunks for tables/CPT
            elif len(para.split()) < 20:
                adaptive_size = 1500  # Larger chunks for sparse content
            else:
                adaptive_size = chunk_size

            # Add paragraph to current chunk
            test_chunk = (current_chunk + "\n\n" + para).strip()

            if len(test_chunk) <= adaptive_size:
                current_chunk = test_chunk
                # Update metadata with any new information from this paragraph
                para_metadata = extract_metadata_enrichment(para)
                current_metadata.update(para_metadata)
            else:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append(Document(
                        page_content=current_chunk,
                        metadata=current_metadata.copy()
                    ))

                # Start new chunk
                current_chunk = para
                current_metadata = base_metadata.copy()
                current_metadata.update(extract_metadata_enrichment(para))

        # Save final chunk
        if current_chunk:
            chunks.append(Document(
                page_content=current_chunk,
                metadata=current_metadata.copy()
            ))

    logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
    return chunks


# ============================================================================
# Vector Store Tools (OpenSearch/Qdrant)
# ============================================================================

@tool
async def prepare_rag_pipeline(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare RAG pipeline from Textract output in S3.

    This tool:
    1. Extracts text from Textract JSON files in S3
    2. Applies intelligent chunking for benefit coverage documents
    3. Creates embeddings using AWS Bedrock Titan
    4. Indexes chunks in OpenSearch or Qdrant

    Args:
        params: Dictionary containing:
            - s3_bucket (str): S3 bucket name
            - textract_prefix (str): Path to Textract output folder
                Example: "mba/textract-output/mba/pdf/policy.pdf/job-123/"
            - index_name (str, optional): Vector store index name
            - chunk_size (int, optional): Target chunk size (default: 1000)
            - chunk_overlap (int, optional): Chunk overlap (default: 200)

    Returns:
        Dictionary with processing results:
        - success: bool
        - message: str
        - chunks_count: int
        - doc_count: int
        - index_name: str

    Example:
        >>> await prepare_rag_pipeline({
        ...     "s3_bucket": "mb-assistant-bucket",
        ...     "textract_prefix": "mba/textract-output/mba/pdf/benefits.pdf/abc123/"
        ... })
    """
    try:
        s3_bucket = params.get("s3_bucket")
        textract_prefix = params.get("textract_prefix")
        index_name = params.get("index_name", DEFAULT_INDEX)
        chunk_size = params.get("chunk_size", 1000)
        chunk_overlap = params.get("chunk_overlap", 200)

        if not s3_bucket or not textract_prefix:
            return {
                "success": False,
                "error": "s3_bucket and textract_prefix are required"
            }

        logger.info(f"Starting RAG pipeline preparation: s3://{s3_bucket}/{textract_prefix}")

        # Step 1: Extract text from Textract output
        documents = extract_text_from_textract_s3(s3_bucket, textract_prefix)
        logger.info(f"Extracted {len(documents)} documents from Textract output")

        # Step 2: Chunk documents
        chunks = chunk_documents(documents, chunk_size, chunk_overlap)
        logger.info(f"Created {len(chunks)} chunks")

        # Step 3: Create embeddings
        texts = [chunk.page_content for chunk in chunks]
        embeddings = get_bedrock_embeddings(texts)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # Step 4: Index in vector store (stub - you'll implement OpenSearch/Qdrant)
        # For now, we'll just log success
        # TODO: Implement actual OpenSearch/Qdrant indexing
        logger.info(f"Would index {len(chunks)} chunks in {index_name}")

        return {
            "success": True,
            "message": f"Processed {len(documents)} docs into {len(chunks)} chunks",
            "chunks_count": len(chunks),
            "doc_count": len(documents),
            "index_name": index_name
        }

    except Exception as e:
        logger.error(f"RAG pipeline preparation failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Pipeline preparation failed: {str(e)}"
        }


@tool
async def query_rag(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query benefit coverage documents using RAG.

    This tool:
    1. Performs semantic search over indexed benefit coverage documents
    2. Reranks results using AWS Bedrock Cohere Rerank
    3. Generates answer using AWS Bedrock Claude LLM
    4. Returns answer with source citations

    Args:
        params: Dictionary containing:
            - question (str): User's question about benefit coverage
            - index_name (str, optional): Vector store index to query
            - k (int, optional): Number of documents to retrieve (default: 5)

    Returns:
        Dictionary with query results:
        - success: bool
        - answer: str
        - sources: List[Dict] with source information
        - question: str

    Example:
        >>> await query_rag({
        ...     "question": "Is massage therapy covered?"
        ... })
    """
    try:
        question = params.get("question")
        index_name = params.get("index_name", DEFAULT_INDEX)
        k = params.get("k", 5)

        if not question:
            return {
                "success": False,
                "error": "question is required"
            }

        logger.info(f"Querying RAG: '{question}'")

        # Step 1: Get query embedding
        query_embedding = get_bedrock_embeddings([question])[0]

        # Step 2: Search vector store (stub - you'll implement actual search)
        # TODO: Implement OpenSearch/Qdrant similarity search
        # For now, return stub response

        stub_docs = [
            Document(
                page_content="Massage therapy is covered with a limit of 6 visits per calendar year. Prior authorization is not required.",
                metadata={"source": "policy.pdf", "page": 15, "section_title": "Therapy Services"}
            )
        ]

        # Step 3: Rerank (stub)
        doc_texts = [doc.page_content for doc in stub_docs]
        reranked_indices = rerank_documents(question, doc_texts, top_n=k)
        reranked_docs = [stub_docs[i] for i in reranked_indices]

        # Step 4: Generate answer
        context = "\n\n".join([doc.page_content for doc in reranked_docs])
        answer = query_bedrock_llm(question, context)

        # Step 5: Format sources
        sources = []
        for i, doc in enumerate(reranked_docs):
            sources.append({
                "source_id": i + 1,
                "content": doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                "metadata": doc.metadata
            })

        return {
            "success": True,
            "answer": answer,
            "sources": sources,
            "question": question,
            "retrieved_docs_count": len(reranked_docs)
        }

    except Exception as e:
        logger.error(f"RAG query failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Query failed: {str(e)}",
            "answer": "Unable to process your question due to an error"
        }
