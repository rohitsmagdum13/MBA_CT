"""Local RAG Agent with Strands SDK integration."""

import os
from strands import Agent

from .tools import upload_pdf_local, prepare_local_rag, query_local_rag
from .prompt import PREP_PROMPT, QUERY_PROMPT
from ...core.settings import settings
from ...core.logging_config import get_logger
from ...core.exceptions import ConfigError

logger = get_logger(__name__)

# Setup AWS credentials for Bedrock (only for LLM, everything else is local)
is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

if not is_lambda:
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        os.environ['AWS_ACCESS_KEY_ID'] = settings.aws_access_key_id
        os.environ['AWS_SECRET_ACCESS_KEY'] = settings.aws_secret_access_key
        os.environ['AWS_DEFAULT_REGION'] = settings.aws_default_region

# Create Strands agent
local_rag_agent = Agent(
    name="LocalRAGAgent",
    system_prompt=QUERY_PROMPT,
    tools=[upload_pdf_local, prepare_local_rag, query_local_rag],
    model=settings.bedrock_model_id
)

logger.info("Local RAG Agent initialized successfully")
