"""
Local RAG Agent with Open-Source Tools.

This package provides a completely local RAG implementation using:
- PyMuPDF (fitz) for PDF text extraction
- Tabula for table extraction
- Sentence Transformers for local embeddings
- ChromaDB for local vector storage
- Cross-encoder for local reranking
- AWS Bedrock Claude for answer generation

No S3, no Textract - everything runs locally except the final LLM.
"""

from .wrapper import LocalRAGAgent

__all__ = ["LocalRAGAgent"]
