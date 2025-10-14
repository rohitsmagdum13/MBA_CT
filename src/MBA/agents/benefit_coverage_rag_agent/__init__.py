"""
Benefit Coverage RAG Agent.

This package provides intelligent retrieval-augmented generation (RAG)
capabilities for querying benefit coverage policies and documents.

The agent:
- Prepares RAG pipelines from Textract-processed PDFs in S3
- Performs semantic search over benefit coverage documents
- Answers policy questions using AWS Bedrock LLM
"""

from .wrapper import BenefitCoverageRAGAgent

__all__ = ["BenefitCoverageRAGAgent"]
