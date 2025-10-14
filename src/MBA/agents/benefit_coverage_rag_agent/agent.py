"""
Benefit Coverage RAG Agent initialization and configuration.

This module establishes the Strands-orchestrated agent that integrates
AWS Bedrock language models with vector-indexed benefit coverage documents
for intelligent policy question answering.

The agent is initialized with:
- Bedrock runtime client (claude-sonnet-4.5 via AWS SDK)
- RAG pipeline preparation and query tools
- Benefit coverage-specific system prompts
- Production-grade logging and error handling

Architecture:
    User Request → Strands Agent → Bedrock LLM → RAG Tools → Vector Store
                                                                   ↓
    JSON Response ← Response Formatting ← Tool Result ← Retrieved Documents
"""

import os
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError

from strands import Agent

from .tools import prepare_rag_pipeline, query_rag
from .prompt import PREP_AGENT_PROMPT, QUERY_AGENT_PROMPT
from ...core.settings import settings
from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError

logger = get_logger(__name__)


def _setup_aws_credentials():
    """
    Set up AWS credentials in environment for Bedrock access.

    Strands Agent will use these credentials automatically when accessing
    Bedrock with a model ID string.

    Side Effects:
        - Sets AWS environment variables if credentials provided in settings
        - Logs credential source
    """
    # Detect Lambda environment
    is_lambda = (
        'AWS_EXECUTION_ENV' in os.environ or
        'AWS_LAMBDA_FUNCTION_NAME' in os.environ
    )

    if is_lambda:
        logger.info("Running in AWS Lambda - using execution role for Bedrock")
        return

    # Set up credentials in environment for Strands/Bedrock
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        os.environ['AWS_ACCESS_KEY_ID'] = settings.aws_access_key_id
        os.environ['AWS_SECRET_ACCESS_KEY'] = settings.aws_secret_access_key
        os.environ['AWS_DEFAULT_REGION'] = settings.aws_default_region
        logger.info("Using explicit AWS credentials from settings")
    elif settings.aws_profile:
        os.environ['AWS_PROFILE'] = settings.aws_profile
        os.environ['AWS_DEFAULT_REGION'] = settings.aws_default_region
        logger.info(f"Using AWS profile: {settings.aws_profile}")
    else:
        logger.info("Using default credential chain (environment/IAM)")

    logger.info(f"AWS region configured: {settings.aws_default_region}")


# Set up AWS credentials for Bedrock
try:
    _setup_aws_credentials()
    logger.info(
        f"Bedrock configuration ready for Benefit Coverage RAG Agent",
        extra={
            "model_id": settings.bedrock_model_id,
            "region": settings.aws_default_region
        }
    )

except Exception as e:
    logger.error(f"Failed to set up AWS credentials for Benefit Coverage RAG Agent: {str(e)}")
    raise ConfigError(
        f"Bedrock setup failed: {str(e)}",
        details={"error_type": type(e).__name__}
    )


# Create Strands agent instance with Bedrock model ID
# The agent starts with query mode by default
benefit_coverage_rag_agent = Agent(
    name="BenefitCoverageRAGAgent",
    system_prompt=QUERY_AGENT_PROMPT,  # Default to query mode
    tools=[prepare_rag_pipeline, query_rag],
    model=settings.bedrock_model_id  # Pass model ID string directly
)

logger.info(
    "Benefit Coverage RAG Agent initialized successfully",
    extra={
        "agent_name": benefit_coverage_rag_agent.name,
        "tools_count": 2,  # prepare_rag_pipeline and query_rag
        "model_type": "AWS Bedrock",
        "model_id": settings.bedrock_model_id
    }
)


def invoke_benefit_coverage_rag_agent(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invoke agent with routing based on input type.

    - If 'textract_prefix' in input: Use prep tool (prepare_rag_pipeline)
    - If 'question' in input: Use query tool (query_rag)

    Args:
        input_data: Dictionary with either:
            - For prep: {"s3_bucket": str, "textract_prefix": str, ...}
            - For query: {"question": str, "index_name": str, ...}

    Returns:
        Dictionary with tool execution results

    Example:
        # Prepare RAG pipeline
        >>> invoke_benefit_coverage_rag_agent({
        ...     "s3_bucket": "mb-assistant-bucket",
        ...     "textract_prefix": "mba/textract-output/mba/pdf/policy.pdf/job-123/"
        ... })

        # Query benefit coverage
        >>> invoke_benefit_coverage_rag_agent({
        ...     "question": "Is massage therapy covered?"
        ... })
    """
    try:
        if 'textract_prefix' in input_data:
            # Preparation mode: switch to prep prompt
            original_prompt = benefit_coverage_rag_agent.system_prompt
            benefit_coverage_rag_agent.system_prompt = PREP_AGENT_PROMPT

            logger.info("Invoking Benefit Coverage RAG Agent in PREP mode")
            result = benefit_coverage_rag_agent(input_data)

            # Restore query prompt
            benefit_coverage_rag_agent.system_prompt = original_prompt
            return result

        elif 'question' in input_data:
            # Query mode: use default query prompt
            logger.info("Invoking Benefit Coverage RAG Agent in QUERY mode")
            result = benefit_coverage_rag_agent(input_data)
            return result

        else:
            error_msg = "Invalid input: Provide 'textract_prefix' for prep or 'question' for query"
            logger.error(error_msg)
            return {"error": error_msg}

    except Exception as e:
        logger.error(f"Agent invocation failed: {str(e)}", exc_info=True)
        return {"error": f"Agent invocation failed: {str(e)}"}
