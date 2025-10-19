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
import uuid

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)

from strands import tool

from ...core.logging_config import get_logger
from ...core.settings import settings
from ...core.exceptions import UploadError, TextractError

logger = get_logger(__name__)

# Configuration
BULK_BATCH_SIZE = int(os.getenv("BULK_BATCH_SIZE", "64"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "1.5"))
VECTOR_FIELD = os.getenv("VECTOR_FIELD", "vector_field")
DEFAULT_INDEX = os.getenv("OPENSEARCH_INDEX", "benefit_coverage_rag_index")
# AWS Bedrock Titan Embeddings v2 produces 1024 dimensions (not 1536)
EMBEDDING_DIMENSION = 1024

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
    logger.info("=" * 80)
    logger.info("STEP: GENERATING EMBEDDINGS WITH AWS BEDROCK TITAN")
    logger.info("=" * 80)
    logger.info(f"📊 Total texts to embed: {len(texts)}")
    logger.info(f"🤖 Model: amazon.titan-embed-text-v2:0")
    logger.info(f"📐 Output dimension: {EMBEDDING_DIMENSION}")

    embeddings = []

    for idx, text in enumerate(texts, 1):
        try:
            text_preview = text[:100] + "..." if len(text) > 100 else text
            logger.info(f"\n🔄 Processing text {idx}/{len(texts)}")
            logger.info(f"   📝 Text length: {len(text)} characters")
            logger.info(f"   📄 Preview: {text_preview}")

            # Truncate to Titan's limit
            truncated_text = text[:8000]
            if len(text) > 8000:
                logger.warning(f"   ⚠️  Text truncated from {len(text)} to 8000 chars (Titan limit)")

            payload = {
                "inputText": truncated_text
            }

            logger.info(f"   🌐 Calling Bedrock Titan API...")
            response = bedrock_runtime.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps(payload)
            )

            result = json.loads(response['body'].read())
            embedding = result['embedding']
            embeddings.append(embedding)

            logger.info(f"   ✅ Embedding generated successfully")
            logger.info(f"   📊 Vector dimension: {len(embedding)}")
            logger.info(f"   🔢 Vector sample (first 5 values): {embedding[:5]}")

        except Exception as e:
            logger.error(f"   ❌ Failed to get embedding for text {idx}: {str(e)[:200]}")
            logger.warning(f"   ⚠️  Using zero vector as fallback for text {idx}")
            # Return zero vector as fallback
            embeddings.append([0.0] * EMBEDDING_DIMENSION)

    logger.info(f"\n✅ EMBEDDING GENERATION COMPLETE")
    logger.info(f"📊 Successfully generated: {len([e for e in embeddings if sum(e) != 0])}/{len(texts)} embeddings")
    logger.info(f"⚠️  Fallback vectors used: {len([e for e in embeddings if sum(e) == 0])}/{len(texts)}")
    logger.info("=" * 80)

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

        # Use cross-region inference profile for Claude (required for on-demand throughput)
        model_id = settings.bedrock_model_id
        if "anthropic.claude" in model_id and not model_id.startswith("us."):
            model_id = f"us.{model_id}"

        response = bedrock_runtime.invoke_model(
            modelId=model_id,
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
    logger.info("=" * 80)
    logger.info("STEP: RERANKING DOCUMENTS WITH AWS BEDROCK COHERE")
    logger.info("=" * 80)
    logger.info(f"🔍 Query: {query}")
    logger.info(f"📚 Documents to rerank: {len(documents)}")
    logger.info(f"🎯 Top N to return: {top_n}")
    logger.info(f"🤖 Model: cohere.rerank-v3-5:0")

    try:
        # Log document previews
        logger.info(f"\n📄 Document previews before reranking:")
        for idx, doc in enumerate(documents):
            preview = doc[:100] + "..." if len(doc) > 100 else doc
            logger.info(f"   Doc {idx}: {preview}")

        payload = {
            "api_version": 2,  # Cohere Rerank v3.5 requires api_version >= 2
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents))
        }

        logger.info(f"\n🌐 Calling Bedrock Cohere Rerank API...")
        response = bedrock_runtime.invoke_model(
            modelId="cohere.rerank-v3-5:0",
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())

        # Extract indices and scores from reranked results
        reranked_results = result.get("results", [])
        reranked_indices = [item["index"] for item in reranked_results]

        logger.info(f"\n✅ RERANKING COMPLETE")
        logger.info(f"📊 Reranking results:")
        for rank, item in enumerate(reranked_results, 1):
            original_idx = item["index"]
            relevance_score = item.get("relevance_score", "N/A")
            doc_preview = documents[original_idx][:80] + "..." if len(documents[original_idx]) > 80 else documents[original_idx]
            logger.info(f"   Rank {rank}: Original Index {original_idx}, Score {relevance_score}")
            logger.info(f"      └─ {doc_preview}")

        logger.info(f"\n🎯 Final reranked indices: {reranked_indices}")
        logger.info("=" * 80)

        return reranked_indices

    except Exception as e:
        logger.error(f"❌ Reranking failed: {str(e)}")
        logger.warning(f"⚠️  Using original document order as fallback")
        logger.info("=" * 80)
        return list(range(len(documents)))


# ============================================================================
# Document Extraction from S3 Textract Output
# ============================================================================

class Document:
    """Simple document class compatible with LangChain."""
    def __init__(self, page_content: str, metadata: Optional[Dict] = None):
        self.page_content = page_content
        self.metadata = metadata or {}


def find_textract_output_path(s3_bucket: str, base_prefix: str) -> str:
    """
    Automatically find the Textract output path by searching S3.

    Handles cases where Textract creates job-specific subfolders.

    Args:
        s3_bucket: S3 bucket name
        base_prefix: Base prefix to search (e.g., "mba/textract-output/mba/pdf/file.pdf/")

    Returns:
        Full prefix to Textract output including job folder if present
    """
    import boto3
    from MBA.core.settings import settings

    logger.info(f"🔍 Auto-detecting Textract output path...")
    logger.info(f"   Base prefix: {base_prefix}")

    # Create S3 client
    if hasattr(settings, 'aws_access_key_id') and settings.aws_access_key_id:
        boto_s3 = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_default_region
        )
    else:
        boto_s3 = boto3.client('s3')

    # List objects with delimiter to find subfolders
    response = boto_s3.list_objects_v2(
        Bucket=s3_bucket,
        Prefix=base_prefix,
        Delimiter='/'
    )

    # Check if there are job ID subfolders
    common_prefixes = response.get('CommonPrefixes', [])

    if common_prefixes:
        # Found subfolders - likely job IDs
        job_folders = [cp['Prefix'] for cp in common_prefixes]
        logger.info(f"   Found {len(job_folders)} subfolder(s):")
        for jf in job_folders:
            logger.info(f"      - {jf}")

        # Use the most recent folder (last in list, assuming alphabetical/time ordering)
        latest_folder = sorted(job_folders)[-1]
        logger.info(f"   ✅ Using latest folder: {latest_folder}")
        return latest_folder

    # No subfolders found, use base prefix directly
    logger.info(f"   ✅ Using base prefix directly (no subfolders)")
    return base_prefix


def extract_text_from_textract_s3(s3_bucket: str, textract_output_prefix: str) -> List[Document]:
    """
    Extract text from Textract JSON files in S3.

    Supports multiple Textract output structures:
    1. Direct structure: s3://{bucket}/{prefix}/page_0001.json
    2. Job ID structure: s3://{bucket}/{prefix}/{job_id}/page_0001.json
    3. With manifest: s3://{bucket}/{prefix}/manifest.json + page_*.json

    Args:
        s3_bucket: S3 bucket name
        textract_output_prefix: Prefix path to Textract output folder

    Returns:
        List of Document objects with extracted text
    """
    logger.info("=" * 80)
    logger.info("STEP: EXTRACTING TEXT FROM TEXTRACT S3 OUTPUT")
    logger.info("=" * 80)
    logger.info(f"📦 S3 Bucket: {s3_bucket}")
    logger.info(f"📁 Textract Prefix (input): {textract_output_prefix}")

    # Auto-detect actual Textract output path (handle job subfolders)
    actual_prefix = find_textract_output_path(s3_bucket, textract_output_prefix)
    logger.info(f"📁 Textract Prefix (detected): {actual_prefix}")
    logger.info(f"🌐 Full S3 Path: s3://{s3_bucket}/{actual_prefix}")

    # Update the prefix to use the detected one
    textract_output_prefix = actual_prefix

    documents = []

    try:
        # List all files in the Textract output folder (including subfolders)
        logger.info(f"\n🔍 Listing objects in S3 (including subfolders)...")

        # Use boto3 directly for better control
        import boto3
        from MBA.core.settings import settings

        # Create S3 client
        if hasattr(settings, 'aws_access_key_id') and settings.aws_access_key_id:
            boto_s3 = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_default_region
            )
        else:
            boto_s3 = boto3.client('s3')

        logger.info(f"📡 Calling S3 ListObjectsV2 API...")
        logger.info(f"   Bucket: {s3_bucket}")
        logger.info(f"   Prefix: {textract_output_prefix}")

        response = boto_s3.list_objects_v2(
            Bucket=s3_bucket,
            Prefix=textract_output_prefix
        )

        logger.info(f"📥 S3 API Response received")
        logger.info(f"   KeyCount: {response.get('KeyCount', 0)}")
        logger.info(f"   IsTruncated: {response.get('IsTruncated', False)}")
        logger.info(f"   Contents present: {'Contents' in response}")

        if 'Contents' not in response or response.get('KeyCount', 0) == 0:
            logger.error(f"❌ No files found in S3 path")
            logger.error(f"📊 Full S3 response: {json.dumps(response, indent=2, default=str)}")
            raise TextractError(
                f"No files found in S3 path: s3://{s3_bucket}/{textract_output_prefix}",
                details={"bucket": s3_bucket, "prefix": textract_output_prefix, "key_count": response.get('KeyCount', 0)}
            )

        # Log all files found
        all_files = [obj['Key'] for obj in response['Contents']]
        logger.info(f"📂 Total files found in prefix: {len(all_files)}")

        # Show first 10 files for debugging
        for f in all_files[:10]:
            logger.info(f"   - {f}")
        if len(all_files) > 10:
            logger.info(f"   ... and {len(all_files) - 10} more files")

        # Filter for page JSON files (handle various naming patterns)
        # Supports: page_0001.json, page_1.json, 0001.json, etc.
        page_files = [
            obj['Key'] for obj in response['Contents']
            if obj['Key'].endswith('.json') and
            ('page_' in obj['Key'].lower() or
             any(char.isdigit() for char in Path(obj['Key']).stem))
        ]

        # Exclude manifest.json and other metadata files
        page_files = [
            f for f in page_files
            if 'manifest' not in f.lower() and
               'metadata' not in f.lower() and
               'consolidated' not in f.lower()
        ]

        if not page_files:
            logger.error(f"❌ No page JSON files found in Textract output")
            logger.warning(f"💡 Hint: Looking for files matching 'page_*.json' or containing digits")
            logger.warning(f"📂 Files found: {[Path(f).name for f in all_files[:20]]}")
            raise TextractError(
                f"No page JSON files found in Textract output",
                details={
                    "bucket": s3_bucket,
                    "prefix": textract_output_prefix,
                    "total_files": len(all_files),
                    "sample_files": [Path(f).name for f in all_files[:10]]
                }
            )

        logger.info(f"\n✅ Found {len(page_files)} Textract page JSON files")
        logger.info(f"📄 Page files to process:")
        for pf in sorted(page_files)[:10]:
            logger.info(f"   - {pf}")
        if len(page_files) > 10:
            logger.info(f"   ... and {len(page_files) - 10} more files")

        # Process each page file
        logger.info(f"\n🔄 Processing Textract page files...")
        for idx, page_file in enumerate(sorted(page_files), 1):
            try:
                logger.info(f"\n{'─' * 60}")
                logger.info(f"Processing Page {idx}/{len(page_files)}: {page_file}")

                # Download JSON file
                logger.info(f"   📥 Downloading from S3...")
                obj = s3_client.get_object(Bucket=s3_bucket, Key=page_file)
                textract_data = json.loads(obj['Body'].read())

                # Extract page number from filename (e.g., page_0001.json -> 1)
                page_num_match = re.search(r'page_(\d+)', page_file)
                page_num = int(page_num_match.group(1)) if page_num_match else 0
                logger.info(f"   📖 Page number: {page_num}")

                # Extract text from Textract blocks
                text_lines = []
                tables = []
                total_blocks = len(textract_data.get('Blocks', []))

                logger.info(f"   🔍 Total Textract blocks: {total_blocks}")

                for block in textract_data.get('Blocks', []):
                    block_type = block.get('BlockType')

                    if block_type == 'LINE' and 'Text' in block:
                        text_lines.append(block['Text'])

                    elif block_type == 'TABLE':
                        # Preserve table structure for better chunking
                        tables.append(f"[TABLE: {block.get('Id', 'unknown')}]")

                logger.info(f"   📝 Extracted LINE blocks: {len(text_lines)}")
                logger.info(f"   📊 Detected TABLE blocks: {len(tables)}")

                # Combine text content
                page_content = '\n'.join(text_lines)
                content_length = len(page_content)

                logger.info(f"   📏 Total text length: {content_length} characters")

                if page_content.strip():
                    # Show preview of extracted text
                    preview = page_content[:200] + "..." if len(page_content) > 200 else page_content
                    logger.info(f"   📄 Text preview: {preview}")

                    doc = Document(
                        page_content=page_content,
                        metadata={
                            "source": page_file,
                            "page": page_num,
                            "s3_bucket": s3_bucket,
                            "s3_key": page_file,
                            "has_tables": len(tables) > 0
                        }
                    )
                    documents.append(doc)
                    logger.info(f"   ✅ Document created with {len(tables)} table markers")
                else:
                    logger.warning(f"   ⚠️  Page {page_num} has no text content, skipping")

            except Exception as e:
                logger.error(f"   ❌ Failed to process page {page_file}: {str(e)}")
                logger.exception(e)
                continue

        if not documents:
            logger.error(f"\n❌ No text extracted from any Textract JSON files")
            raise TextractError(
                "No text extracted from Textract JSON files",
                details={"bucket": s3_bucket, "prefix": textract_output_prefix, "files_processed": len(page_files)}
            )

        logger.info(f"\n{'=' * 80}")
        logger.info(f"✅ TEXT EXTRACTION COMPLETE")
        logger.info(f"📊 Summary:")
        logger.info(f"   - Total pages processed: {len(page_files)}")
        logger.info(f"   - Documents created: {len(documents)}")
        logger.info(f"   - Pages with tables: {sum(1 for d in documents if d.metadata.get('has_tables'))}")
        total_chars = sum(len(d.page_content) for d in documents)
        logger.info(f"   - Total characters extracted: {total_chars:,}")
        logger.info("=" * 80)

        return documents

    except ClientError as e:
        logger.error(f"❌ S3 ClientError: {str(e)}")
        raise UploadError(
            f"S3 error accessing Textract output: {str(e)}",
            details={"bucket": s3_bucket, "prefix": textract_output_prefix}
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        logger.exception(e)
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
    logger.info("=" * 80)
    logger.info("STEP: INTELLIGENT DOCUMENT CHUNKING")
    logger.info("=" * 80)
    logger.info(f"📚 Documents to chunk: {len(documents)}")
    logger.info(f"📏 Default chunk size: {chunk_size} characters")
    logger.info(f"🔄 Chunk overlap: {chunk_overlap} characters")
    logger.info(f"\n💡 Chunking Strategy:")
    logger.info(f"   - Tables/CPT codes: 600 chars (smaller for dense content)")
    logger.info(f"   - Sparse content (<20 words): 1500 chars (larger chunks)")
    logger.info(f"   - Normal text: {chunk_size} chars")
    logger.info(f"   - Preserve paragraph boundaries")
    logger.info(f"   - Extract metadata (section, category, CPT codes, etc.)")

    chunks = []

    for doc_idx, doc in enumerate(documents, 1):
        logger.info(f"\n{'─' * 60}")
        logger.info(f"Processing Document {doc_idx}/{len(documents)}")
        logger.info(f"   📄 Source: {doc.metadata.get('source', 'unknown')}")
        logger.info(f"   📖 Page: {doc.metadata.get('page', 'N/A')}")
        logger.info(f"   📏 Length: {len(doc.page_content)} characters")

        text = doc.page_content
        base_metadata = doc.metadata.copy()

        # Split by double newline (paragraph boundaries)
        paragraphs = re.split(r'\n\s*\n', text)
        logger.info(f"   📝 Paragraphs detected: {len(paragraphs)}")

        current_chunk = ""
        current_metadata = base_metadata.copy()
        chunk_count_for_doc = 0

        for para_idx, para in enumerate(paragraphs, 1):
            para = para.strip()
            if not para:
                continue

            # Check if paragraph is a table
            is_table = detect_table(para)

            # Determine chunk size based on content
            word_count = len(para.split())
            if is_table or re.search(r'\bCPT\b', para, flags=re.IGNORECASE):
                adaptive_size = 600  # Smaller chunks for tables/CPT
                content_type = "TABLE/CPT"
            elif word_count < 20:
                adaptive_size = 1500  # Larger chunks for sparse content
                content_type = "SPARSE"
            else:
                adaptive_size = chunk_size
                content_type = "NORMAL"

            # Log paragraph analysis
            if para_idx <= 3:  # Log first 3 paragraphs in detail
                para_preview = para[:100] + "..." if len(para) > 100 else para
                logger.info(f"\n   Para {para_idx}: Type={content_type}, Size={len(para)} chars, Words={word_count}")
                logger.info(f"      Adaptive chunk size: {adaptive_size}")
                logger.info(f"      Preview: {para_preview}")

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
                    chunk_count_for_doc += 1
                    chunks.append(Document(
                        page_content=current_chunk,
                        metadata=current_metadata.copy()
                    ))

                    if chunk_count_for_doc <= 2:  # Log first 2 chunks in detail
                        logger.info(f"\n   ✅ Chunk {chunk_count_for_doc} created:")
                        logger.info(f"      Length: {len(current_chunk)} chars")
                        logger.info(f"      Metadata: {current_metadata}")
                        chunk_preview = current_chunk[:150] + "..." if len(current_chunk) > 150 else current_chunk
                        logger.info(f"      Content: {chunk_preview}")

                # Start new chunk
                current_chunk = para
                current_metadata = base_metadata.copy()
                current_metadata.update(extract_metadata_enrichment(para))

        # Save final chunk
        if current_chunk:
            chunk_count_for_doc += 1
            chunks.append(Document(
                page_content=current_chunk,
                metadata=current_metadata.copy()
            ))

        logger.info(f"\n   ✅ Document {doc_idx} produced {chunk_count_for_doc} chunks")

    logger.info(f"\n{'=' * 80}")
    logger.info(f"✅ CHUNKING COMPLETE")
    logger.info(f"📊 Summary:")
    logger.info(f"   - Total documents processed: {len(documents)}")
    logger.info(f"   - Total chunks created: {len(chunks)}")
    logger.info(f"   - Average chunks per document: {len(chunks)/len(documents):.1f}")

    # Analyze chunk size distribution
    chunk_sizes = [len(c.page_content) for c in chunks]
    logger.info(f"   - Min chunk size: {min(chunk_sizes)} chars")
    logger.info(f"   - Max chunk size: {max(chunk_sizes)} chars")
    logger.info(f"   - Average chunk size: {sum(chunk_sizes)/len(chunk_sizes):.0f} chars")

    # Count metadata enrichment
    chunks_with_cpt = sum(1 for c in chunks if c.metadata.get('cpt_codes'))
    chunks_with_category = sum(1 for c in chunks if c.metadata.get('benefit_category'))
    logger.info(f"   - Chunks with CPT codes: {chunks_with_cpt}")
    logger.info(f"   - Chunks with benefit category: {chunks_with_category}")
    logger.info("=" * 80)

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

        # Step 4: Index in Qdrant
        logger.info("=" * 80)
        logger.info("STEP: INDEXING IN QDRANT VECTOR STORE")
        logger.info("=" * 80)
        logger.info(f"🗄️  Qdrant URL: {settings.qdrant_url}")
        logger.info(f"📁 Collection name: {index_name}")
        logger.info(f"📐 Vector dimension: {EMBEDDING_DIMENSION}")
        logger.info(f"📏 Distance metric: COSINE")

        try:
            logger.info(f"\n🔌 Connecting to Qdrant...")
            qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                timeout=60
            )
            logger.info(f"✅ Connected to Qdrant successfully")

            # Create collection if not exists
            logger.info(f"\n🔍 Checking if collection '{index_name}' exists...")
            collections = qdrant_client.get_collections().collections
            existing = [c.name for c in collections]
            logger.info(f"📚 Existing collections: {existing}")

            if index_name not in existing:
                logger.info(f"\n🆕 Collection '{index_name}' does not exist, creating...")
                qdrant_client.recreate_collection(
                    collection_name=index_name,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIMENSION,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Created new Qdrant collection: {index_name}")
            else:
                logger.info(f"✅ Collection '{index_name}' already exists, will upsert points")

            # Build vector points
            logger.info(f"\n🔨 Building vector points for indexing...")
            points = []
            for idx, (chunk, vector) in enumerate(zip(chunks, embeddings), 1):
                content_hash = hashlib.sha256(chunk.page_content.encode()).hexdigest()
                uid = str(uuid.UUID(content_hash[:32]))

                if idx <= 3:  # Log first 3 points in detail
                    logger.info(f"\n   Point {idx}:")
                    logger.info(f"      ID: {uid}")
                    logger.info(f"      Vector dimension: {len(vector)}")
                    logger.info(f"      Vector sample: {vector[:3]}")
                    logger.info(f"      Payload keys: {list(chunk.metadata.keys())}")
                    text_preview = chunk.page_content[:100] + "..." if len(chunk.page_content) > 100 else chunk.page_content
                    logger.info(f"      Text preview: {text_preview}")

                points.append(PointStruct(
                    id=uid,
                    vector=vector,
                    payload={"text": chunk.page_content, **chunk.metadata}
                ))

            logger.info(f"\n✅ Built {len(points)} vector points")

            # Bulk upload to Qdrant
            logger.info(f"\n📤 Upserting {len(points)} points to Qdrant collection '{index_name}'...")
            qdrant_client.upsert(collection_name=index_name, points=points)

            logger.info(f"\n✅ INDEXING COMPLETE")
            logger.info(f"📊 Successfully indexed {len(points)} chunks into Qdrant collection '{index_name}'")

            # Get collection info
            collection_info = qdrant_client.get_collection(index_name)
            logger.info(f"📈 Collection info:")
            logger.info(f"   - Total vectors: {collection_info.points_count}")
            logger.info(f"   - Vector dimension: {collection_info.config.params.vectors.size}")
            logger.info(f"   - Distance metric: {collection_info.config.params.vectors.distance}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Qdrant indexing failed: {str(e)}")
            logger.exception(e)
            logger.info("=" * 80)
            return {"success": False, "error": f"Indexing failed: {str(e)}"}

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

        logger.info("=" * 80)
        logger.info("STEP 1: GENERATING QUERY EMBEDDING")
        logger.info("=" * 80)
        logger.info(f"🔍 Query: {question}")
        logger.info(f"📏 Query length: {len(question)} characters")

        # Step 1: Get query embedding
        query_embedding = get_bedrock_embeddings([question])[0]

        logger.info(f"✅ Query embedding generated")
        logger.info(f"📐 Embedding dimension: {len(query_embedding)}")
        logger.info(f"🔢 Embedding sample: {query_embedding[:5]}")

        # Step 2: Search Qdrant
        logger.info("=" * 80)
        logger.info("STEP 2: SEMANTIC SEARCH IN VECTOR STORE")
        logger.info("=" * 80)
        logger.info(f"🗄️  Qdrant URL: {settings.qdrant_url}")
        logger.info(f"📁 Collection: {index_name}")
        logger.info(f"🎯 Retrieving top k={k} documents")

        try:
            logger.info(f"\n🔌 Connecting to Qdrant...")
            qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                timeout=60
            )
            logger.info(f"✅ Connected successfully")

            logger.info(f"\n🔍 Performing vector similarity search...")
            search_results = qdrant_client.search(
                collection_name=index_name,
                query_vector=query_embedding,
                limit=k
            )

            logger.info(f"✅ Search complete, found {len(search_results)} results")

            retrieved_docs = []
            logger.info(f"\n📄 Retrieved documents:")
            for idx, hit in enumerate(search_results, 1):
                payload = hit.payload
                score = hit.score

                doc = Document(
                    page_content=payload.get("text", ""),
                    metadata={k: v for k, v in payload.items() if k != "text"}
                )
                retrieved_docs.append(doc)

                # Log each result
                doc_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                logger.info(f"\n   Result {idx}:")
                logger.info(f"      Score: {score:.4f}")
                logger.info(f"      Source: {doc.metadata.get('source', 'unknown')}")
                logger.info(f"      Page: {doc.metadata.get('page', 'N/A')}")
                logger.info(f"      Text length: {len(doc.page_content)} chars")
                logger.info(f"      Preview: {doc_preview}")

            logger.info(f"\n✅ Retrieved {len(retrieved_docs)} documents from Qdrant")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Qdrant search failed: {str(e)}")
            logger.exception(e)
            logger.info("=" * 80)
            return {"success": False, "error": f"Vector search failed: {str(e)}"}

        # Step 3: Rerank
        doc_texts = [doc.page_content for doc in retrieved_docs]
        reranked_indices = rerank_documents(question, doc_texts, top_n=k)
        reranked_docs = [retrieved_docs[i] for i in reranked_indices]

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
