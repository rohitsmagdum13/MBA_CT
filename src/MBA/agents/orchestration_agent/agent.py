"""
Strands Agent configuration for Orchestration Agent.

This module initializes the Strands-based orchestration agent using AWS Bedrock
Claude Sonnet 4.5 for intelligent multi-agent routing and coordination.
"""

import os
import sys
from typing import Dict, Any

import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError

from strands import Agent

from ...core.logging_config import setup_root_logger, get_logger
from ...core.settings import settings
from ...core.exceptions import ConfigError

from .prompt import ORCHESTRATION_PROMPT
from .tools import analyze_query, route_to_agent, format_response

# Setup logging
setup_root_logger()
logger = get_logger(__name__)


def _setup_aws_credentials() -> Dict[str, str]:
    """
    Configure AWS credentials for Bedrock access.

    Returns:
        Dictionary with AWS configuration

    Raises:
        ConfigError: If credentials are missing or invalid
    """
    # Check if running in Lambda
    is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

    if is_lambda:
        logger.info("Running in Lambda - using execution role")
        return {
            'region_name': settings.aws_default_region
        }
    else:
        logger.info("Using explicit AWS credentials from settings")

        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            raise ConfigError(
                "AWS credentials not configured",
                details={"required": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]}
            )

        # Set environment variables for boto3
        os.environ['AWS_ACCESS_KEY_ID'] = settings.aws_access_key_id
        os.environ['AWS_SECRET_ACCESS_KEY'] = settings.aws_secret_access_key
        os.environ['AWS_DEFAULT_REGION'] = settings.aws_default_region

        logger.info(f"AWS region configured: {settings.aws_default_region}")

        return {
            'region_name': settings.aws_default_region,
            'aws_access_key_id': settings.aws_access_key_id,
            'aws_secret_access_key': settings.aws_secret_access_key
        }


# Configure AWS
try:
    aws_config = _setup_aws_credentials()
    logger.info("Bedrock configuration ready for Orchestration Agent")
except ConfigError as e:
    logger.error(f"AWS configuration failed: {e.message}", extra=e.details)
    raise
except Exception as e:
    logger.error(f"Unexpected error during AWS setup: {str(e)}")
    raise ConfigError(f"AWS setup failed: {str(e)}")

# Initialize Strands Agent
try:
    orchestration_agent = Agent(
        name="OrchestrationAgent",
        system_prompt=ORCHESTRATION_PROMPT,
        tools=[analyze_query, route_to_agent, format_response],
        model=settings.bedrock_model_id
    )

    logger.info("Orchestration Agent initialized successfully")
    logger.info(f"Model: {settings.bedrock_model_id}")
    logger.info("Tools: analyze_query, route_to_agent, format_response")
    logger.info("Orchestration Agent ready for intelligent multi-agent routing")

except Exception as e:
    logger.error(f"Failed to initialize Orchestration Agent: {str(e)}")
    raise ConfigError(
        "Agent initialization failed",
        details={"error": str(e), "model": settings.bedrock_model_id}
    )
