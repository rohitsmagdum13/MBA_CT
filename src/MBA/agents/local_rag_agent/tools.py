"""
Local RAG Tools using Open-Source Libraries.

This module provides completely local RAG capabilities:
1. PDF upload and local storage
2. Text extraction using PyMuPDF + Tabula
3. Local embeddings using Sentence Transformers
4. Local vector storage using ChromaDB
5. Local reranking using Cross-encoder
6. Answer generation using Bedrock Claude
"""

import os
import json
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import shutil

# PDF Processing
import fitz  # PyMuPDF
import pdfplumber
import tabula

# Embeddings & Vector Store
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb
from chromadb.config import Settings

# AWS Bedrock for LLM
import boto3
from botocore.exceptions import ClientError

# Strands
from strands import tool

# Internal
from ...core.logging_config import get_logger
from ...core.settings import settings

logger = get_logger(__name__)

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store"

# Create directories
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

# Model Configuration
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dimensions, fast
# EMBEDDING_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"  # 768 dimensions, better quality
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Initialize models (lazy loading)
_embedding_model = None
_reranker_model = None
_chroma_client = None
_bedrock_client = None


def get_embedding_model():
    """Get or initialize embedding model."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info(f"Embedding model loaded. Dimension: {_embedding_model.get_sentence_embedding_dimension()}")
    return _embedding_model


def get_reranker_model():
    """Get or initialize reranker model."""
    global _reranker_model
    if _reranker_model is None:
        logger.info(f"Loading reranker model: {RERANKER_MODEL_NAME}")
        _reranker_model = CrossEncoder(RERANKER_MODEL_NAME)
        logger.info("Reranker model loaded")
    return _reranker_model


def get_chroma_client():
    """Get or initialize ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        logger.info(f"Initializing ChromaDB at {VECTOR_STORE_DIR}")
        _chroma_client = chromadb.PersistentClient(
            path=str(VECTOR_STORE_DIR),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        logger.info("ChromaDB client initialized")
    return _chroma_client


def get_bedrock_client():
    """Get or initialize AWS Bedrock client."""
    global _bedrock_client
    if _bedrock_client is None:
        # Detect Lambda environment
        is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

        if is_lambda:
            session = boto3.Session(region_name=settings.aws_default_region)
        else:
            session_kwargs = {'region_name': settings.aws_default_region}
            if settings.aws_profile:
                session_kwargs["profile_name"] = settings.aws_profile
            elif settings.aws_access_key_id and settings.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            session = boto3.Session(**session_kwargs)

        _bedrock_client = session.client('bedrock-runtime', region_name=settings.aws_default_region)
        logger.info("Bedrock client initialized")
    return _bedrock_client


# ============================================================================
# PDF Text Extraction
# ============================================================================

class Document:
    """Simple document class."""
    def __init__(self, page_content: str, metadata: Optional[Dict] = None):
        self.page_content = page_content
        self.metadata = metadata or {}


def extract_text_with_pymupdf(pdf_path: Path) -> List[Document]:
    """
    Extract text from PDF using PyMuPDF (fitz).

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of Document objects, one per page
    """
    documents = []

    try:
        pdf_document = fitz.open(pdf_path)

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]

            # Extract text
            text = page.get_text("text")

            # Extract images count
            image_list = page.get_images()

            # Get page dimensions
            rect = page.rect

            if text.strip():
                documents.append(Document(
                    page_content=text,
                    metadata={
                        "source": pdf_path.name,
                        "page": page_num + 1,
                        "total_pages": len(pdf_document),
                        "width": rect.width,
                        "height": rect.height,
                        "images_count": len(image_list),
                        "extraction_method": "pymupdf"
                    }
                ))

        pdf_document.close()
        logger.info(f"Extracted {len(documents)} pages from {pdf_path.name} using PyMuPDF")

    except Exception as e:
        logger.error(f"PyMuPDF extraction failed for {pdf_path.name}: {str(e)}")
        raise

    return documents


def extract_tables_with_tabula(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF using Tabula.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of table dictionaries with data and metadata
    """
    tables_data = []

    try:
        # Extract all tables from PDF
        tables = tabula.read_pdf(
            str(pdf_path),
            pages='all',
            multiple_tables=True,
            lattice=True,  # Better for tables with lines
            stream=True    # Better for tables without lines
        )

        for i, df in enumerate(tables):
            if df is not None and not df.empty:
                # Convert DataFrame to markdown table format
                table_md = df.to_markdown(index=False)

                # Also get JSON representation
                table_json = df.to_dict(orient='records')

                tables_data.append({
                    "table_id": i + 1,
                    "markdown": table_md,
                    "json": table_json,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "columns_list": df.columns.tolist()
                })

        logger.info(f"Extracted {len(tables_data)} tables from {pdf_path.name} using Tabula")

    except Exception as e:
        logger.warning(f"Tabula table extraction failed for {pdf_path.name}: {str(e)}")
        # Non-fatal: continue without tables

    return tables_data


def extract_tables_with_pdfplumber(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF using pdfplumber (backup method).

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of table dictionaries
    """
    tables_data = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()

                for table_num, table in enumerate(tables):
                    if table and len(table) > 0:
                        # Convert to markdown-like format
                        table_text = "\n".join([" | ".join([str(cell) for cell in row]) for row in table])

                        tables_data.append({
                            "table_id": f"page_{page_num+1}_table_{table_num+1}",
                            "page": page_num + 1,
                            "text": table_text,
                            "rows": len(table),
                            "columns": len(table[0]) if table else 0
                        })

        logger.info(f"Extracted {len(tables_data)} tables from {pdf_path.name} using pdfplumber")

    except Exception as e:
        logger.warning(f"pdfplumber table extraction failed for {pdf_path.name}: {str(e)}")

    return tables_data


def extract_pdf_comprehensive(pdf_path: Path) -> Dict[str, Any]:
    """
    Comprehensive PDF extraction combining text and tables.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary with extracted content and metadata
    """
    logger.info(f"Starting comprehensive extraction for {pdf_path.name}")

    # Extract text pages
    text_documents = extract_text_with_pymupdf(pdf_path)

    # Extract tables (try both methods)
    tables_tabula = extract_tables_with_tabula(pdf_path)
    tables_pdfplumber = extract_tables_with_pdfplumber(pdf_path)

    # Combine tables (prefer Tabula, use pdfplumber as backup)
    all_tables = tables_tabula if tables_tabula else tables_pdfplumber

    # Create comprehensive document structure
    extraction_result = {
        "file_name": pdf_path.name,
        "file_path": str(pdf_path),
        "file_size_mb": pdf_path.stat().st_size / (1024 * 1024),
        "extracted_at": datetime.utcnow().isoformat(),
        "total_pages": len(text_documents),
        "pages": [],
        "tables": all_tables,
        "table_count": len(all_tables)
    }

    # Add page-level data
    for doc in text_documents:
        page_data = {
            "page_number": doc.metadata["page"],
            "text": doc.page_content,
            "char_count": len(doc.page_content),
            "word_count": len(doc.page_content.split()),
            "images_count": doc.metadata.get("images_count", 0),
            "has_tables": False  # Will be updated if tables found on this page
        }

        # Check if any tables belong to this page
        for table in all_tables:
            if table.get("page") == doc.metadata["page"]:
                page_data["has_tables"] = True
                break

        extraction_result["pages"].append(page_data)

    # Save extraction result as JSON
    output_json_path = PROCESSED_DIR / f"{pdf_path.stem}_extracted.json"
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(extraction_result, f, indent=2, ensure_ascii=False)

    logger.info(f"Extraction saved to {output_json_path}")
    logger.info(f"Extracted {len(text_documents)} pages and {len(all_tables)} tables")

    return extraction_result


# ============================================================================
# Intelligent Chunking (Same as before)
# ============================================================================

def detect_table(text: str) -> bool:
    """Detect if text contains tabular data."""
    if '|' in text and re.search(r'\|.+\|', text):
        return True
    if re.search(r'\bCPT\b.*\d{5}', text, flags=re.IGNORECASE):
        return True
    lines = [l for l in text.splitlines() if l.strip()]
    multi_col_lines = sum(1 for l in lines if len(re.findall(r'\s{3,}', l)) >= 2)
    return multi_col_lines >= max(2, len(lines) // 5)


def extract_metadata_enrichment(text: str) -> Dict[str, Any]:
    """Extract metadata from benefit coverage text."""
    metadata = {}

    section_match = re.search(r'^#{1,3}\s*(.+)$', text, flags=re.MULTILINE)
    if section_match:
        metadata["section_title"] = section_match.group(1).strip()

    if re.search(r'\b(therapy|physical therapy|occupational therapy)\b', text, flags=re.IGNORECASE):
        metadata["benefit_category"] = "Therapy Services"
    elif re.search(r'\b(diagnostic|imaging|radiology|mri|ct scan)\b', text, flags=re.IGNORECASE):
        metadata["benefit_category"] = "Diagnostic Services"
    elif re.search(r'\b(preventive|wellness|screening)\b', text, flags=re.IGNORECASE):
        metadata["benefit_category"] = "Preventive Care"

    if re.search(r'\b(covered|eligible|benefit)\b', text, flags=re.IGNORECASE):
        metadata["coverage_type"] = "covered"
    elif re.search(r'\b(excluded|not covered|limitation)\b', text, flags=re.IGNORECASE):
        metadata["coverage_type"] = "excluded"
    elif re.search(r'\b(prior authorization|preauthorization|pre-cert)\b', text, flags=re.IGNORECASE):
        metadata["coverage_type"] = "prior_auth_required"

    cpt_matches = re.findall(r'\b(\d{5})\b', text)
    if cpt_matches:
        metadata["cpt_codes"] = list(set(cpt_matches))[:10]

    if re.search(r'\$([\d,]+)', text):
        metadata["has_cost_info"] = True

    return metadata


def chunk_documents(documents: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
    """Intelligently chunk benefit coverage documents."""
    chunks = []

    for doc in documents:
        text = doc.page_content
        base_metadata = doc.metadata.copy()

        paragraphs = re.split(r'\n\s*\n', text)

        current_chunk = ""
        current_metadata = base_metadata.copy()

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            is_table = detect_table(para)

            if is_table or re.search(r'\bCPT\b', para, flags=re.IGNORECASE):
                adaptive_size = 600
            elif len(para.split()) < 20:
                adaptive_size = 1500
            else:
                adaptive_size = chunk_size

            test_chunk = (current_chunk + "\n\n" + para).strip()

            if len(test_chunk) <= adaptive_size:
                current_chunk = test_chunk
                para_metadata = extract_metadata_enrichment(para)
                current_metadata.update(para_metadata)
            else:
                if current_chunk:
                    chunks.append(Document(
                        page_content=current_chunk,
                        metadata=current_metadata.copy()
                    ))

                current_chunk = para
                current_metadata = base_metadata.copy()
                current_metadata.update(extract_metadata_enrichment(para))

        if current_chunk:
            chunks.append(Document(
                page_content=current_chunk,
                metadata=current_metadata.copy()
            ))

    logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
    return chunks


# ============================================================================
# Local Embeddings & Vector Store
# ============================================================================

def create_embeddings_local(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using local Sentence Transformer model."""
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    return embeddings.tolist()


def rerank_local(query: str, documents: List[str], top_n: int = 5) -> List[int]:
    """Rerank documents using local cross-encoder model."""
    try:
        reranker = get_reranker_model()

        # Create pairs of (query, document)
        pairs = [[query, doc] for doc in documents]

        # Get relevance scores
        scores = reranker.predict(pairs)

        # Get indices sorted by score (descending)
        ranked_indices = scores.argsort()[::-1][:top_n].tolist()

        return ranked_indices

    except Exception as e:
        logger.warning(f"Local reranking failed, using original order: {str(e)}")
        return list(range(min(top_n, len(documents))))


def query_bedrock_llm(prompt: str, context: str, max_tokens: int = 2000) -> str:
    """Query AWS Bedrock Claude for answer generation."""
    try:
        bedrock = get_bedrock_client()

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

        response = bedrock.invoke_model(
            modelId=settings.bedrock_model_id,
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        return result['content'][0]['text']

    except Exception as e:
        logger.error(f"Bedrock LLM query failed: {str(e)}")
        return f"Error generating answer: {str(e)}"


# ============================================================================
# Tool Functions
# ============================================================================

@tool
async def upload_pdf_local(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upload PDF to local storage and extract content.

    Args:
        params: Dictionary containing:
            - file_path (str): Path to PDF file to upload
            - extract_now (bool): Whether to extract immediately (default: True)

    Returns:
        Dictionary with upload and extraction results
    """
    try:
        source_path = Path(params.get("file_path"))
        extract_now = params.get("extract_now", True)

        if not source_path.exists():
            return {"success": False, "error": f"File not found: {source_path}"}

        if source_path.suffix.lower() != '.pdf':
            return {"success": False, "error": "Only PDF files are supported"}

        # Copy to uploads directory
        dest_path = UPLOAD_DIR / source_path.name
        shutil.copy2(source_path, dest_path)

        logger.info(f"PDF uploaded to {dest_path}")

        result = {
            "success": True,
            "uploaded_file": str(dest_path),
            "file_name": dest_path.name,
            "file_size_mb": round(dest_path.stat().st_size / (1024 * 1024), 2)
        }

        # Extract if requested
        if extract_now:
            extraction = extract_pdf_comprehensive(dest_path)
            result["extraction"] = {
                "pages": extraction["total_pages"],
                "tables": extraction["table_count"],
                "json_path": str(PROCESSED_DIR / f"{dest_path.stem}_extracted.json")
            }

        return result

    except Exception as e:
        logger.error(f"PDF upload failed: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Upload failed: {str(e)}"}


@tool
async def prepare_local_rag(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare local RAG pipeline from extracted JSON.

    Args:
        params: Dictionary containing:
            - json_path (str): Path to extracted JSON file
            - collection_name (str): ChromaDB collection name
            - chunk_size (int): Chunk size (default: 1000)
            - chunk_overlap (int): Chunk overlap (default: 200)

    Returns:
        Dictionary with preparation results
    """
    try:
        json_path = Path(params.get("json_path"))
        collection_name = params.get("collection_name", "local_benefit_coverage")
        chunk_size = params.get("chunk_size", 1000)
        chunk_overlap = params.get("chunk_overlap", 200)

        if not json_path.exists():
            return {"success": False, "error": f"JSON file not found: {json_path}"}

        # Load extraction JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            extraction_data = json.load(f)

        # Convert to Document objects
        documents = []
        for page in extraction_data["pages"]:
            documents.append(Document(
                page_content=page["text"],
                metadata={
                    "source": extraction_data["file_name"],
                    "page": page["page_number"],
                    "has_tables": page.get("has_tables", False),
                    "word_count": page.get("word_count", 0)
                }
            ))

        # Chunk documents
        chunks = chunk_documents(documents, chunk_size, chunk_overlap)

        # Generate embeddings
        texts = [chunk.page_content for chunk in chunks]
        embeddings = create_embeddings_local(texts)

        # Initialize ChromaDB
        chroma_client = get_chroma_client()

        # Delete collection if exists (for fresh indexing)
        try:
            chroma_client.delete_collection(name=collection_name)
        except:
            pass

        # Create collection
        collection = chroma_client.create_collection(
            name=collection_name,
            metadata={"description": "Local benefit coverage documents"}
        )

        # Add documents to collection
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        metadatas = [chunk.metadata for chunk in chunks]

        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Indexed {len(chunks)} chunks in collection '{collection_name}'")

        return {
            "success": True,
            "message": f"Processed {len(documents)} pages into {len(chunks)} chunks",
            "chunks_count": len(chunks),
            "doc_count": len(documents),
            "collection_name": collection_name,
            "embedding_model": EMBEDDING_MODEL_NAME
        }

    except Exception as e:
        logger.error(f"Local RAG preparation failed: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Preparation failed: {str(e)}"}


@tool
async def query_local_rag(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query local RAG system.

    Args:
        params: Dictionary containing:
            - question (str): User question
            - collection_name (str): ChromaDB collection name
            - k (int): Number of documents to retrieve (default: 5)
            - use_reranker (bool): Whether to use reranker (default: True)

    Returns:
        Dictionary with answer and sources
    """
    try:
        question = params.get("question")
        collection_name = params.get("collection_name", "local_benefit_coverage")
        k = params.get("k", 5)
        use_reranker = params.get("use_reranker", True)

        if not question:
            return {"success": False, "error": "question is required"}

        # Get embedding for question
        query_embedding = create_embeddings_local([question])[0]

        # Query ChromaDB
        chroma_client = get_chroma_client()
        collection = chroma_client.get_collection(name=collection_name)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k * 2 if use_reranker else k  # Get more for reranking
        )

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]

        # Rerank if requested
        if use_reranker and len(documents) > 1:
            reranked_indices = rerank_local(question, documents, top_n=k)
            documents = [documents[i] for i in reranked_indices]
            metadatas = [metadatas[i] for i in reranked_indices]
            distances = [distances[i] for i in reranked_indices]
        else:
            documents = documents[:k]
            metadatas = metadatas[:k]
            distances = distances[:k]

        # Generate answer using Bedrock Claude
        context = "\n\n".join(documents)
        answer = query_bedrock_llm(question, context)

        # Format sources
        sources = []
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            sources.append({
                "source_id": i + 1,
                "content": doc[:500] + "..." if len(doc) > 500 else doc,
                "metadata": meta,
                "similarity_score": round(1 - dist, 4)  # Convert distance to similarity
            })

        return {
            "success": True,
            "answer": answer,
            "sources": sources,
            "question": question,
            "retrieved_docs_count": len(documents),
            "embedding_model": EMBEDDING_MODEL_NAME,
            "reranker_used": use_reranker
        }

    except Exception as e:
        logger.error(f"Local RAG query failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Query failed: {str(e)}",
            "answer": "Unable to process your question due to an error"
        }
