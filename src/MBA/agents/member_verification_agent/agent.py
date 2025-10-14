"""
Member Verification Agent initialization and configuration.

This module establishes the Strands-orchestrated agent that integrates
AWS Bedrock language models with RDS MySQL member data for identity
authentication workflows.

The agent is initialized with:
- Bedrock runtime client (claude-sonnet-4.5 via AWS SDK)
- Member verification tools
- Strict JSON response system prompt
- Production-grade logging and error handling

Architecture:
    User Request → Strands Agent → Bedrock LLM → verify_member Tool → RDS MySQL
                                                                        ↓
    JSON Response ← Response Formatting ← Tool Result ← SQL Query Result
"""

import os
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError

from strands import Agent

from .tools import verify_member
from .prompt import SYSTEM_PROMPT
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
        f"Bedrock configuration ready",
        extra={
            "model_id": settings.bedrock_model_id,
            "region": settings.aws_default_region
        }
    )

except Exception as e:
    logger.error(f"Failed to set up AWS credentials: {str(e)}")
    raise ConfigError(
        f"Bedrock setup failed: {str(e)}",
        details={"error_type": type(e).__name__}
    )


# Create Strands agent instance with Bedrock model ID
# Strands Agent will automatically create a BedrockModel client using the model_id string
verification_agent = Agent(
    name="MemberVerificationAgent",
    system_prompt=SYSTEM_PROMPT,
    tools=[verify_member],
    model=settings.bedrock_model_id  # Pass model ID string directly
)

logger.info(
    "Member Verification Agent initialized successfully",
    extra={
        "agent_name": verification_agent.name,
        "tools_count": 1,  # verify_member tool
        "model_type": "AWS Bedrock",
        "model_id": settings.bedrock_model_id
    }
)
