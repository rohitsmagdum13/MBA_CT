"""Wrapper for Local RAG Agent."""

from typing import Dict, Any, Optional
from pathlib import Path

from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError

logger = get_logger(__name__)


class LocalRAGAgent:
    """Production wrapper for local RAG operations."""

    def __init__(self):
        """Initialize Local RAG Agent wrapper."""
        self._initialized = False
        logger.info("LocalRAGAgent wrapper created")

    def _ensure_initialized(self):
        """Lazy initialization."""
        if self._initialized:
            return

        try:
            from . import agent
            self._initialized = True
            logger.info("Local RAG Agent initialized on first use")
        except Exception as e:
            logger.error(f"Failed to initialize local RAG agent: {e}")
            raise RuntimeError(f"Agent initialization failed: {str(e)}")

    async def upload_pdf(self, file_path: str, filename: Optional[str] = None, extract_now: bool = True) -> Dict[str, Any]:
        """
        Upload PDF and optionally extract content.

        Args:
            file_path: Path to PDF file
            filename: Original filename to use (optional, defaults to file_path name)
            extract_now: Whether to extract immediately

        Returns:
            Upload and extraction results
        """
        try:
            self._ensure_initialized()

            from .tools import upload_pdf_local

            params = {"file_path": file_path, "extract_now": extract_now}
            if filename:
                params["filename"] = filename
            result = await upload_pdf_local(params)

            logger.info(f"PDF upload completed: {result.get('file_name')}")
            return result

        except Exception as e:
            logger.error(f"PDF upload failed: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Upload failed: {str(e)}"}

    async def prepare_pipeline(
        self,
        json_path: str,
        collection_name: str = "local_benefit_coverage",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Dict[str, Any]:
        """
        Prepare local RAG pipeline from extracted JSON.

        Args:
            json_path: Path to extracted JSON file
            collection_name: ChromaDB collection name
            chunk_size: Chunk size
            chunk_overlap: Chunk overlap

        Returns:
            Preparation results
        """
        try:
            self._ensure_initialized()

            from .tools import prepare_local_rag

            params = {
                "json_path": json_path,
                "collection_name": collection_name,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap
            }

            logger.info(f"Preparing local RAG pipeline from {json_path}")
            result = await prepare_local_rag(params)

            logger.info(f"Pipeline preparation completed: {result.get('chunks_count')} chunks indexed")
            return result

        except Exception as e:
            logger.error(f"Pipeline preparation failed: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Preparation failed: {str(e)}"}

    async def query(
        self,
        question: str,
        collection_name: str = "local_benefit_coverage",
        k: int = 5,
        use_reranker: bool = True
    ) -> Dict[str, Any]:
        """
        Query local RAG system.

        Args:
            question: User question
            collection_name: ChromaDB collection name
            k: Number of documents to retrieve
            use_reranker: Whether to use reranker

        Returns:
            Answer with sources
        """
        try:
            self._ensure_initialized()

            from .tools import query_local_rag

            params = {
                "question": question,
                "collection_name": collection_name,
                "k": k,
                "use_reranker": use_reranker
            }

            logger.info(f"Querying local RAG: {question[:100]}")
            result = await query_local_rag(params)

            logger.info(f"Query completed: {len(result.get('sources', []))} sources retrieved")
            return result

        except Exception as e:
            logger.error(f"Query failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Query failed: {str(e)}",
                "answer": "Unable to process your question due to an error"
            }
