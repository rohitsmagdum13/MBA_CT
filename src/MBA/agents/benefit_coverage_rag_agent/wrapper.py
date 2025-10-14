"""
High-level wrapper for Benefit Coverage RAG Agent.

This module provides a production-grade OOP interface to the Strands-based
benefit coverage RAG agent, encapsulating initialization, invocation, error handling,
and result processing.

The wrapper enables:
- Clean async interface for RAG preparation and query workflows
- Structured exception handling with detailed error context
- Comprehensive logging for audit trails
- Type-safe parameter validation
- Graceful degradation on failures

Usage:
    agent = BenefitCoverageRAGAgent()
    # Prepare pipeline
    result = await agent.prepare_pipeline(s3_bucket="...", textract_prefix="...")
    # Query documents
    result = await agent.query(question="Is massage therapy covered?")
"""

from typing import Dict, Any, Optional

from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError, UploadError, TextractError

logger = get_logger(__name__)


class BenefitCoverageRAGAgent:
    """
    Production wrapper for AWS Bedrock-powered benefit coverage RAG.

    Provides a clean async interface to the Strands agent orchestration
    layer, handling initialization, parameter validation, and result
    normalization for RAG preparation and query workflows.

    This class integrates:
    - AWS Bedrock language models via boto3
    - S3 Textract output processing
    - Vector store (OpenSearch/Qdrant) for document indexing
    - Strands agent orchestration framework
    - Structured logging and error handling

    Attributes:
        _initialized: Initialization state flag

    Thread Safety:
        Not thread-safe. Create separate instances per thread/task.
    """

    def __init__(self):
        """
        Initialize Benefit Coverage RAG Agent wrapper.

        Lazy-loads the tool functions to defer initialization until first use.
        This pattern supports efficient Lambda cold starts and testing scenarios.

        Side Effects:
            - Logs wrapper initialization
            - Defers agent initialization to first invocation
        """
        self._initialized = False
        logger.info("BenefitCoverageRAGAgent wrapper created")

    def _ensure_initialized(self):
        """
        Lazy initialization of underlying tools and agent.

        Loads the RAG agent on first use, enabling fast cold starts
        and reducing initialization overhead in testing environments.

        Raises:
            ConfigError: If agent cannot be initialized
            RuntimeError: If agent module import fails

        Side Effects:
            - Imports agent module
            - Initializes Bedrock client
            - Registers RAG tools
            - Sets _initialized flag
        """
        if self._initialized:
            return

        try:
            # Import agent to trigger initialization
            from . import agent
            self._initialized = True
            logger.info("Benefit Coverage RAG Agent initialized on first use")

        except ImportError as e:
            logger.error(f"Failed to import benefit coverage RAG agent: {e}")
            raise RuntimeError(
                f"Agent initialization failed: Cannot import agent module - {str(e)}"
            )

        except ConfigError as e:
            logger.error(f"Agent configuration error: {e.message}", extra=e.details)
            raise

        except Exception as e:
            logger.error(f"Unexpected error initializing agent: {str(e)}")
            raise RuntimeError(f"Agent initialization failed: {str(e)}")

    async def prepare_pipeline(
        self,
        s3_bucket: str,
        textract_prefix: str,
        index_name: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Dict[str, Any]:
        """
        Prepare RAG pipeline from Textract output in S3.

        Orchestrates the complete pipeline preparation workflow:
        1. Extract text from Textract JSON files in S3
        2. Apply intelligent chunking for benefit coverage documents
        3. Generate embeddings using AWS Bedrock Titan
        4. Index documents in vector store (OpenSearch/Qdrant)

        Args:
            s3_bucket: S3 bucket containing Textract output
            textract_prefix: S3 prefix path to Textract output folder
                Example: "mba/textract-output/mba/pdf/policy.pdf/job-123/"
            index_name: Vector store index name (optional)
            chunk_size: Target chunk size in characters (default: 1000)
            chunk_overlap: Overlap between chunks (default: 200)

        Returns:
            Dictionary containing preparation results:
            - success: bool
            - message: str (summary)
            - chunks_count: int
            - doc_count: int
            - index_name: str

        Raises:
            ValueError: If required parameters not provided
            RuntimeError: If agent execution fails

        Example:
            >>> agent = BenefitCoverageRAGAgent()
            >>> result = await agent.prepare_pipeline(
            ...     s3_bucket="mb-assistant-bucket",
            ...     textract_prefix="mba/textract-output/mba/pdf/benefits.pdf/abc123/"
            ... )
            >>> print(result)
            {
                "success": True,
                "message": "Processed 10 docs into 45 chunks",
                "chunks_count": 45,
                "doc_count": 10,
                "index_name": "benefit_coverage_rag_index"
            }

        Side Effects:
            - Downloads Textract JSON from S3
            - Creates embeddings via Bedrock API calls
            - Writes to vector store (OpenSearch/Qdrant)
            - Logs preparation progress and results
        """
        # Validate parameters
        if not s3_bucket:
            logger.error("Pipeline preparation attempted without s3_bucket")
            raise ValueError("s3_bucket is required")

        if not textract_prefix:
            logger.error("Pipeline preparation attempted without textract_prefix")
            raise ValueError("textract_prefix is required")

        # Build parameters
        params = {
            "s3_bucket": s3_bucket,
            "textract_prefix": textract_prefix,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap
        }

        if index_name:
            params["index_name"] = index_name

        logger.info(
            f"RAG pipeline preparation requested",
            extra={
                "s3_bucket": s3_bucket,
                "textract_prefix": textract_prefix,
                "index_name": index_name,
                "chunk_size": chunk_size
            }
        )

        # Ensure agent initialized
        try:
            self._ensure_initialized()
        except (ConfigError, RuntimeError) as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {"success": False, "error": f"RAG service unavailable: {str(e)}"}

        # Execute pipeline preparation via direct tool call
        try:
            logger.info("=" * 60)
            logger.info("EXECUTING RAG PIPELINE PREPARATION")
            logger.info("=" * 60)

            # WORKAROUND: Call tool directly (same pattern as other agents)
            from .tools import prepare_rag_pipeline

            logger.info(f"Calling prepare_rag_pipeline tool with params: {params}")
            result = await prepare_rag_pipeline(params)

            logger.info(
                f"Pipeline preparation completed",
                extra={
                    "success": result.get("success", False),
                    "has_error": "error" in result
                }
            )
            logger.info("=" * 60)

            return result

        except UploadError as e:
            logger.error(
                f"S3 error during pipeline preparation: {e.message}",
                extra=e.details
            )
            return {"success": False, "error": "Pipeline preparation failed: S3 error"}

        except TextractError as e:
            logger.error(
                f"Textract error during pipeline preparation: {e.message}",
                extra=e.details
            )
            return {"success": False, "error": "Pipeline preparation failed: Textract error"}

        except Exception as e:
            logger.error(
                f"Pipeline preparation failed: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )
            return {"success": False, "error": f"Pipeline preparation failed: {str(e)}"}

    async def query(
        self,
        question: str,
        index_name: Optional[str] = None,
        k: int = 5
    ) -> Dict[str, Any]:
        """
        Query benefit coverage documents using RAG.

        Orchestrates the complete query workflow:
        1. Generate query embedding via Bedrock
        2. Search vector store for relevant documents
        3. Rerank results using Bedrock Cohere Rerank
        4. Generate answer using Bedrock Claude LLM
        5. Return answer with source citations

        Args:
            question: User's question about benefit coverage (required)
            index_name: Vector store index to query (optional)
            k: Number of documents to retrieve (default: 5)

        Returns:
            Dictionary containing query results:
            - success: bool
            - answer: str (generated answer)
            - sources: List[Dict] (source citations)
            - question: str (original question)
            - retrieved_docs_count: int

        Raises:
            ValueError: If question not provided
            RuntimeError: If agent execution fails

        Example:
            >>> agent = BenefitCoverageRAGAgent()
            >>> result = await agent.query(
            ...     question="Is massage therapy covered?"
            ... )
            >>> print(result["answer"])
            "Massage therapy is covered with a limit of 6 visits per calendar year..."

        Side Effects:
            - Queries Bedrock for embeddings
            - Searches vector store
            - Calls Bedrock for reranking and answer generation
            - Logs query attempts and results
        """
        # Validate question
        if not question:
            logger.error("Query attempted without question")
            raise ValueError("question is required")

        # Build parameters
        params = {"question": question, "k": k}

        if index_name:
            params["index_name"] = index_name

        logger.info(
            f"RAG query requested",
            extra={
                "question": question[:100],  # Truncate for logging
                "index_name": index_name,
                "k": k
            }
        )

        # Ensure agent initialized
        try:
            self._ensure_initialized()
        except (ConfigError, RuntimeError) as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {
                "success": False,
                "error": f"RAG service unavailable: {str(e)}",
                "answer": "Unable to process query due to service unavailability"
            }

        # Execute query via direct tool call
        try:
            logger.info("=" * 60)
            logger.info("EXECUTING RAG QUERY")
            logger.info("=" * 60)

            # WORKAROUND: Call tool directly
            from .tools import query_rag

            logger.info(f"Calling query_rag tool with question: {question[:100]}...")
            result = await query_rag(params)

            logger.info(
                f"Query completed",
                extra={
                    "success": result.get("success", False),
                    "has_answer": "answer" in result,
                    "source_count": len(result.get("sources", []))
                }
            )
            logger.info("=" * 60)

            return result

        except Exception as e:
            logger.error(
                f"Query execution failed: {str(e)}",
                exc_info=True,
                extra={"error_type": type(e).__name__}
            )

            return {
                "success": False,
                "error": f"Query failed: {str(e)}",
                "answer": "Unable to process your question due to an error"
            }
