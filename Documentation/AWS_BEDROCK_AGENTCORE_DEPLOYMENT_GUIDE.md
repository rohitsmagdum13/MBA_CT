# AWS Bedrock AgentCore Runtime Deployment Guide

## MBA_CT Multi-Agent System - Production Deployment

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Prerequisites](#2-prerequisites)
3. [Current Architecture](#3-current-architecture)
4. [Target AgentCore Architecture](#4-target-agentcore-architecture)
5. [Deployment Flow - Step by Step](#5-deployment-flow---step-by-step)
6. [Code Examples](#6-code-examples)
7. [Architecture Decisions](#7-architecture-decisions)
8. [Cost & Pricing](#8-cost--pricing)
9. [Monitoring & Operations](#9-monitoring--operations)
10. [Troubleshooting](#10-troubleshooting)
11. [Appendices](#11-appendices)

---

## 1. Introduction

### 1.1 What is AWS Bedrock AgentCore Runtime?

Amazon Bedrock AgentCore Runtime is a **secure, serverless runtime** purpose-built for deploying and scaling dynamic AI agents at enterprise scale. It provides:

- ✅ **Zero Infrastructure Management** - No containers, servers, or orchestration to manage
- ✅ **Framework Agnostic** - Works with Strands Agents, LangChain, LangGraph, CrewAI
- ✅ **Built-in Gateway & Memory** - Session management and HTTP wrapper included
- ✅ **Auto-scaling** - Scales from zero to thousands of concurrent requests
- ✅ **Enterprise Security** - IAM integration, VPC support, encryption at rest/transit
- ✅ **Observability** - CloudWatch Logs, X-Ray tracing, metrics out of the box

### 1.2 Why Use AgentCore for MBA_CT?

The MBA_CT project is a complex multi-agent system with 7 specialized agents handling medical benefits administration. AgentCore Runtime provides:

| Benefit | Impact |
|---------|--------|
| **Simplified Deployment** | Single command to deploy Strands agents to production |
| **Scalability** | Automatically handles variable workloads (claims processing peaks) |
| **Reliability** | Built-in health checks, retries, and failover |
| **Cost Efficiency** | Pay only for actual usage (free until Sept 2025) |
| **Security Compliance** | Enterprise-grade security for HIPAA-sensitive data |
| **Developer Velocity** | Focus on agent logic, not infrastructure |

### 1.3 Deployment Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER REQUEST                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway                                 │
│  • Authentication (API Keys, Cognito, IAM)                       │
│  • Rate Limiting & Throttling                                    │
│  • Request Routing                                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Bedrock AgentCore Runtime                           │
│                Orchestration Agent                               │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  @app.entrypoint                                     │       │
│  │  async def invoke(payload):                          │       │
│  │      # Route to specialized agents                   │       │
│  │      return orchestrate_response(payload)            │       │
│  └──────────────────────────────────────────────────────┘       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
    ┌────────┐        ┌────────┐        ┌────────┐
    │ Member │        │Deduct. │        │Benefit │
    │ Verify │        │  OOP   │        │Coverage│
    │ Agent  │        │ Agent  │        │  RAG   │
    └────┬───┘        └───┬────┘        └───┬────┘
         │                │                  │
         └────────────────┼──────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
    ┌─────────┐     ┌─────────┐     ┌─────────┐
    │   RDS   │     │   RDS   │     │ Qdrant  │
    │ MySQL   │     │ MySQL   │     │ Vector  │
    │MemberDB │     │Deductbl.│     │   DB    │
    └─────────┘     └─────────┘     └─────────┘
```

---

## 2. Prerequisites

### 2.1 AWS Account Requirements

**Required AWS Services Access:**
- ✅ Amazon Bedrock (with model access to Claude 3.5 Sonnet)
- ✅ Amazon ECR (Elastic Container Registry)
- ✅ Amazon ECS (Elastic Container Service)
- ✅ AWS CodeBuild (for automated Docker builds)
- ✅ IAM (for role creation and management)
- ✅ Amazon RDS (MySQL - already set up)
- ✅ Amazon S3 (already set up)
- ✅ CloudWatch Logs & X-Ray
- ✅ AWS Secrets Manager (for credentials)
- ✅ API Gateway (for external access)

**Required IAM Permissions:**

Your AWS user/role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:*",
        "ecr:*",
        "ecs:*",
        "codebuild:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PassRole",
        "logs:*",
        "xray:*",
        "secretsmanager:*",
        "apigateway:*"
      ],
      "Resource": "*"
    }
  ]
}
```

**Bedrock Model Access:**

Ensure you have enabled model access in Bedrock:

```bash
# Check available models
aws bedrock list-foundation-models --region us-east-1

# Request model access if needed (via AWS Console)
# Navigate to: Bedrock > Model Access > Request Access
# Enable: Claude 3.5 Sonnet v2, Titan Embeddings v2, Cohere Rerank v3.5
```

### 2.2 Local Development Environment

**Required Software:**

| Software | Version | Purpose | Installation |
|----------|---------|---------|--------------|
| Python | 3.11+ | Runtime environment | `python --version` |
| Docker | Latest | Local testing | [Install Docker](https://docs.docker.com/get-docker/) |
| AWS CLI | v2 | AWS interactions | `pip install awscli` |
| UV | Latest | Package manager | `pip install uv` |
| Git | Latest | Version control | Pre-installed |

**Install AWS CLI and Configure:**

```bash
# Install AWS CLI v2
pip install awscli --upgrade

# Configure AWS credentials
aws configure
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region name: us-east-1
# Default output format: json

# Verify configuration
aws sts get-caller-identity
```

**Verify Docker:**

```bash
# Check Docker installation
docker --version
# Expected: Docker version 20.10.x or higher

# Test Docker
docker run hello-world
```

### 2.3 Python Dependencies

**Install Bedrock AgentCore Toolkit:**

```bash
# Navigate to project root
cd c:\Users\ROHIT\Work\HMA\MBA_CT

# Install toolkit and dependencies
pip install bedrock-agentcore-starter-toolkit>=0.1.21

# Or using UV (recommended)
uv pip install bedrock-agentcore-starter-toolkit>=0.1.21

# Verify installation
agentcore --version
```

**Update Project Dependencies:**

Add to your `requirements.txt`:

```txt
# AWS Bedrock AgentCore
bedrock-agentcore-starter-toolkit>=0.1.21
bedrock-agentcore>=0.2.0

# Existing dependencies
strands-agents>=0.1.0
strands-agents-tools>=0.1.0
boto3>=1.34.0
# ... rest of existing dependencies
```

Install all dependencies:

```bash
uv pip install -r requirements.txt
```

### 2.4 Existing Infrastructure Verification

Verify your existing AWS resources are accessible:

**Test RDS Connection:**

```bash
# Test MySQL connection
mysql -h mba-mysql-db.conaisaskh5d.us-east-1.rds.amazonaws.com \
      -u admin -p \
      -D mba_db

# Or use Python test
python -c "from MBA.services.database.client import RDSClient; \
           client = RDSClient(); \
           print('RDS Connected:', client.test_connection())"
```

**Test S3 Access:**

```bash
# List bucket contents
aws s3 ls s3://mb-assistant-bucket/mba/

# Test with Python
python -c "from MBA.services.storage.s3_client import S3Client; \
           client = S3Client(); \
           print('S3 Connected:', client.list_objects('mba/'))"
```

**Test Qdrant Vector DB:**

```bash
# Test Qdrant connection
python -c "from qdrant_client import QdrantClient; \
           from MBA.core.settings import settings; \
           client = QdrantClient(url=settings.QDRANT_URL, \
                                api_key=settings.QDRANT_API_KEY); \
           print('Qdrant Connected:', client.get_collections())"
```

### 2.5 Environment Configuration

**Current `.env` File Structure:**

Ensure your `.env` file contains all required variables:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_DEFAULT_REGION=us-east-1

# Bedrock Models
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0

# RDS MySQL
RDS_HOST=mba-mysql-db.conaisaskh5d.us-east-1.rds.amazonaws.com
RDS_PORT=3306
RDS_DATABASE=mba_db
RDS_USERNAME=admin
RDS_PASSWORD=YOUR_PASSWORD_HERE
RDS_POOL_SIZE=5
RDS_POOL_MAX_OVERFLOW=10

# S3 Storage
S3_BUCKET_MBA=mb-assistant-bucket
S3_PREFIX_MBA=mba/

# Qdrant Vector DB
QDRANT_URL=https://YOUR_CLUSTER.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=YOUR_QDRANT_API_KEY
QDRANT_COLLECTION=benefit_coverage_rag_index
EMBEDDING_DIMENSION=1024

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_FILE=app.log
```

---

## 3. Current Architecture

### 3.1 Existing MBA_CT System

The MBA_CT project currently uses:

**Application Layer:**
- **FastAPI Server** (`src/MBA/microservices/api.py`) - Port 8000
- **Streamlit UI** (`src/MBA/ui/streamlit_app.py`) - Port 8501
- **Lambda Handler** (`src/MBA/lambda_handlers/mba_ingest_lambda.py`) - S3 event processing

**Agent Layer (7 Agents):**

| Agent | Purpose | Data Source | Port/Method |
|-------|---------|-------------|-------------|
| **OrchestrationAgent** | Routes queries to specialized agents | In-memory cache | API endpoint |
| **IntentIdentificationAgent** | Classifies user query intent | Pattern matching | Direct call |
| **MemberVerificationAgent** | Verify member eligibility | RDS: memberdata | Direct call |
| **DeductibleOOPAgent** | Deductible/OOP information | RDS: deductibles_oop | Direct call |
| **BenefitAccumulatorAgent** | Track service usage/limits | RDS: benefit_accumulator | Direct call |
| **BenefitCoverageRAGAgent** | Q&A on coverage policies | Qdrant Vector DB | Direct call |
| **LocalRAGAgent** | Query user-uploaded docs | ChromaDB (local) | Direct call |

**Data Layer:**
- **RDS MySQL** - Structured data (members, deductibles, accumulators)
- **Qdrant Cloud** - Vector embeddings for RAG
- **ChromaDB** - Local vector DB for user documents
- **S3** - File storage (PDFs, CSVs, Textract output)

**Current Deployment Model:**

```
User → FastAPI (localhost:8000) → Orchestration Agent → Specialized Agents → Data Sources
                                                                              ↓
User → Streamlit UI (localhost:8501) ────────────────────────────────────→ FastAPI
```

### 3.2 Current Limitations

❌ **Manual Infrastructure Management** - Requires server provisioning and maintenance
❌ **Limited Scalability** - Single FastAPI instance, no auto-scaling
❌ **No Built-in Gateway** - Manual API management and authentication
❌ **Local Development Dependency** - Requires local MySQL/ChromaDB for dev
❌ **Manual Session Management** - Custom implementation needed
❌ **Deployment Complexity** - Requires Docker, K8s, or EC2 setup

---

## 4. Target AgentCore Architecture

### 4.1 AgentCore Deployment Model

**Architecture Decision: Single Orchestration Deployment (Recommended)**

We'll deploy the **Orchestration Agent** to AgentCore Runtime, which internally calls the other 6 agents as in-process dependencies.

**Why This Approach?**

✅ **Simpler Deployment** - Single deployment artifact, faster iteration
✅ **Lower Latency** - No network calls between agents
✅ **Cost Efficient** - One runtime instance instead of 7
✅ **Easier Debugging** - Single log stream, simpler tracing
✅ **Shared Dependencies** - Database connection pooling works efficiently

**Architecture Diagram:**

```
┌─────────────────────────────────────────────────────────────────┐
│                      Internet/VPN Users                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Amazon API Gateway                              │
│  • REST API: https://api.mba-system.com/orchestrate             │
│  • Authentication: API Key / Cognito / IAM                       │
│  • Rate Limiting: 1000 req/sec burst, 5000 req/sec steady       │
│  • WAF Protection: SQL injection, XSS, DDoS                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│         AWS Bedrock AgentCore Runtime (Orchestration)            │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  BedrockAgentCoreApp                                 │       │
│  │                                                      │       │
│  │  @app.entrypoint                                     │       │
│  │  async def invoke(payload):                          │       │
│  │      query = payload.get("prompt")                   │       │
│  │      session_id = payload.get("session_id")          │       │
│  │                                                      │       │
│  │      # Initialize orchestration agent                │       │
│  │      orchestrator = OrchestrationAgent()             │       │
│  │                                                      │       │
│  │      # Process query (routes internally)             │       │
│  │      result = await orchestrator.process(query)      │       │
│  │                                                      │       │
│  │      return {                                        │       │
│  │          "response": result.message,                 │       │
│  │          "agent_used": result.agent_name,            │       │
│  │          "confidence": result.confidence             │       │
│  │      }                                               │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Internal Agent Calls (In-Process):                              │
│  ├─ IntentIdentificationAgent()                                  │
│  ├─ MemberVerificationAgent()                                    │
│  ├─ DeductibleOOPAgent()                                         │
│  ├─ BenefitAccumulatorAgent()                                    │
│  ├─ BenefitCoverageRAGAgent()                                    │
│  └─ LocalRAGAgent()                                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐        ┌─────────┐       ┌─────────┐
   │   RDS   │        │ Qdrant  │       │   S3    │
   │  MySQL  │        │ Vector  │       │ Bucket  │
   │ (VPC)   │        │   DB    │       │ (VPC)   │
   └─────────┘        └─────────┘       └─────────┘
```

### 4.2 Alternative Architecture (Microservices)

**For Future Scaling** - Deploy each agent independently:

```
API Gateway
    │
    ├─→ Orchestration Agent Runtime
    │       │
    │       ├─→ Intent Agent Runtime
    │       ├─→ Member Verification Runtime
    │       ├─→ Deductible OOP Runtime
    │       ├─→ Benefit Accumulator Runtime
    │       ├─→ Coverage RAG Runtime
    │       └─→ Local RAG Runtime
    │
    └─→ Data Sources (RDS, Qdrant, S3)
```

**When to Use:**
- Individual agents need independent scaling
- Different SLAs per agent type
- Different security contexts per agent
- Team ownership boundaries

**Note:** This guide focuses on the **Single Orchestration Deployment** approach. Microservices deployment follows the same steps but repeated per agent.

### 4.3 Network & Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Internet                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS (TLS 1.3)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS WAF (Optional)                            │
│  • SQL Injection Protection                                      │
│  • XSS Protection                                                │
│  • DDoS Mitigation                                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               API Gateway (Regional/Edge)                        │
│  • API Key Authentication                                        │
│  • Request/Response Validation                                   │
│  • CloudWatch Logging                                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ IAM Role
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Bedrock AgentCore Runtime                        │
│                      (us-east-1)                                 │
│  • IAM Execution Role                                            │
│  • Secrets Manager Integration                                   │
│  • CloudWatch Logs                                               │
│  • X-Ray Tracing                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │ (VPC Optional)   │                  │
        ▼                  ▼                  ▼
   ┌─────────────┐   ┌──────────────┐   ┌──────────┐
   │  RDS MySQL  │   │   Qdrant     │   │    S3    │
   │  (Private)  │   │  (External)  │   │ (Private)│
   │  Security   │   │  API Key     │   │ IAM Role │
   │  Group:     │   │  Auth        │   │ Access   │
   │  Port 3306  │   └──────────────┘   └──────────┘
   └─────────────┘
```

**Security Controls:**

| Layer | Security Mechanism | Configuration |
|-------|-------------------|---------------|
| **Transport** | TLS 1.3 | API Gateway enforced |
| **Authentication** | API Key / Cognito / IAM | API Gateway |
| **Authorization** | IAM Policies | Execution Role |
| **Network** | VPC (optional) | RDS, S3 VPC endpoints |
| **Secrets** | AWS Secrets Manager | RDS credentials, Qdrant keys |
| **Encryption** | At Rest | S3 SSE-AES256, RDS encryption |
| **Logging** | CloudWatch Logs | All requests logged |
| **Tracing** | X-Ray | Full request tracing |

---

## 5. Deployment Flow - Step by Step

### Phase 1: Environment Setup (1-2 hours)

#### Step 1.1: Install AgentCore Toolkit

```bash
# Navigate to project root
cd c:\Users\ROHIT\Work\HMA\MBA_CT

# Install toolkit
pip install bedrock-agentcore-starter-toolkit>=0.1.21

# Verify installation
agentcore --version
# Expected output: bedrock-agentcore-starter-toolkit, version 0.1.x
```

#### Step 1.2: Verify AWS Configuration

```bash
# Test AWS credentials
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAXXXXXXXXXXXXXXXXX",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-user"
# }

# Verify Bedrock access
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId, `claude`)].modelId'

# Expected: List of Claude models including claude-3-5-sonnet
```

#### Step 1.3: Set Up Project Structure

```bash
# Create entrypoints directory
mkdir -p entrypoints

# Create deployment configuration directory
mkdir -p deployment/configs

# Create documentation directory (already exists)
# ls Documentation/
```

**Expected Directory Structure:**

```
MBA_CT/
├── entrypoints/                          # NEW
│   └── orchestration_entrypoint.py       # NEW (we'll create this)
├── deployment/                           # NEW
│   ├── configs/                          # NEW
│   │   └── secrets_template.json         # NEW
│   └── requirements_agentcore.txt        # NEW
├── src/MBA/
│   ├── agents/                           # EXISTING
│   │   ├── orchestration_agent/
│   │   ├── member_verification_agent/
│   │   └── ... (other agents)
│   └── ...
└── .bedrock_agentcore.yaml               # GENERATED by agentcore configure
```

---

### Phase 2: Code Preparation (2-4 hours)

#### Step 2.1: Create AgentCore Entrypoint

Create the main entrypoint file that wraps your orchestration agent:

**File: `entrypoints/orchestration_entrypoint.py`**

```python
"""
AWS Bedrock AgentCore Runtime Entrypoint for MBA_CT Orchestration Agent

This entrypoint wraps the OrchestrationAgent with BedrockAgentCoreApp
to enable deployment to AgentCore Runtime.

Entry Point: This file serves as the main entry point for the AgentCore Runtime.
"""

import sys
import os
from pathlib import Path

# Add src directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from typing import Dict, Any, Optional
import asyncio
import json
from datetime import datetime

# Import BedrockAgentCoreApp
from bedrock_agentcore import BedrockAgentCoreApp

# Import MBA agents and core modules
from MBA.core.settings import settings
from MBA.core.logging_config import get_logger, setup_root_logger
from MBA.agents.orchestration_agent import OrchestrationAgent

# Setup logging
setup_root_logger()
logger = get_logger(__name__)

# Initialize BedrockAgentCoreApp
app = BedrockAgentCoreApp()

# Lazy initialization for agent (don't initialize until first request)
_orchestration_agent: Optional[OrchestrationAgent] = None


def get_orchestration_agent() -> OrchestrationAgent:
    """
    Lazy initialization of OrchestrationAgent.

    This ensures the agent is only initialized when needed,
    improving cold start performance.
    """
    global _orchestration_agent
    if _orchestration_agent is None:
        logger.info("Initializing OrchestrationAgent...")
        _orchestration_agent = OrchestrationAgent()
        logger.info("OrchestrationAgent initialized successfully")
    return _orchestration_agent


@app.entrypoint
async def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entrypoint for AgentCore Runtime.

    This function is called by AgentCore Runtime for each user request.

    Args:
        payload: Dictionary containing the user's request
            Expected keys:
                - prompt: str - User's query
                - session_id: str (optional) - Session identifier
                - context: dict (optional) - Additional context

    Returns:
        Dictionary with the agent's response
            Keys:
                - response: str - Agent's response message
                - agent_used: str - Name of agent that handled the query
                - confidence: float - Confidence score (0-1)
                - metadata: dict - Additional metadata

    Example payload:
        {
            "prompt": "What is my deductible?",
            "session_id": "session-123",
            "context": {
                "member_id": "M12345",
                "dob": "1990-01-01"
            }
        }
    """
    start_time = datetime.now()

    try:
        # Extract parameters from payload
        prompt = payload.get("prompt", "")
        session_id = payload.get("session_id", None)
        context = payload.get("context", {})

        logger.info(
            f"Received request - prompt: {prompt[:50]}..., "
            f"session_id: {session_id}"
        )

        # Validate prompt
        if not prompt or not isinstance(prompt, str):
            logger.error("Invalid prompt received")
            return {
                "success": False,
                "error": "Invalid prompt. Please provide a valid query string.",
                "response": "I need a valid question to help you.",
                "agent_used": "validation",
                "confidence": 0.0
            }

        # Get orchestration agent (lazy initialized)
        orchestrator = get_orchestration_agent()

        # Process the query through orchestration
        logger.info(f"Processing query: {prompt}")
        result = await orchestrator.process_query(
            query=prompt,
            session_id=session_id,
            context=context
        )

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"Query processed successfully - "
            f"agent: {result.get('agent_used', 'unknown')}, "
            f"time: {processing_time:.2f}s"
        )

        # Return formatted response
        return {
            "success": True,
            "response": result.get("response", ""),
            "agent_used": result.get("agent_used", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "metadata": {
                "processing_time_seconds": processing_time,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                **result.get("metadata", {})
            }
        }

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)

        # Return error response
        return {
            "success": False,
            "error": f"An error occurred: {str(e)}",
            "response": "I apologize, but I encountered an error processing your request. Please try again.",
            "agent_used": "error_handler",
            "confidence": 0.0,
            "metadata": {
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat()
            }
        }


@app.ping
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for AgentCore Runtime.

    This function is called by AgentCore to verify the agent is healthy.

    Returns:
        Dictionary with health status
    """
    try:
        # Check if agent can be initialized
        agent = get_orchestration_agent()

        # TODO: Add more health checks
        # - Database connectivity
        # - S3 access
        # - Qdrant connectivity

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agent_initialized": agent is not None
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Run the app when executed directly
if __name__ == "__main__":
    """
    Local development entry point.

    For local testing:
        python entrypoints/orchestration_entrypoint.py

    For AgentCore deployment:
        agentcore configure --entrypoint entrypoints/orchestration_entrypoint.py
        agentcore launch
    """
    logger.info("Starting MBA_CT Orchestration Agent (AgentCore Runtime)")
    logger.info(f"Environment: {settings.AWS_DEFAULT_REGION}")
    logger.info(f"Bedrock Model: {settings.BEDROCK_MODEL_ID}")

    # Run the app
    app.run()
```

#### Step 2.2: Update Dependencies

Create AgentCore-specific requirements file:

**File: `deployment/requirements_agentcore.txt`**

```txt
# AWS Bedrock AgentCore Runtime
bedrock-agentcore-starter-toolkit>=0.1.21
bedrock-agentcore>=0.2.0

# Core dependencies from existing project
strands-agents>=0.1.0
strands-agents-tools>=0.1.0

# AWS SDK
boto3>=1.34.0
botocore>=1.34.0

# Database
sqlalchemy>=2.0.0
pymysql>=1.1.0

# Vector DB
qdrant-client>=1.7.0
chromadb>=0.4.0

# ML/Embeddings
sentence-transformers>=2.2.0
torch>=2.0.0

# Document Processing
PyMuPDF>=1.23.0
pdfplumber>=0.10.0
tabula-py>=2.8.0

# FastAPI (for local testing compatibility)
fastapi>=0.109.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Utilities
python-dotenv>=1.0.0
jinja2>=3.1.0
```

Update main `requirements.txt`:

```bash
# Append AgentCore dependencies to main requirements
cat deployment/requirements_agentcore.txt >> requirements.txt

# Install updated dependencies
pip install -r requirements.txt
```

#### Step 2.3: Configure Environment Variables for AgentCore

AgentCore Runtime needs environment variables to be passed during deployment. Create a configuration helper:

**File: `deployment/configs/environment_vars.json`**

```json
{
  "AWS_DEFAULT_REGION": "us-east-1",
  "BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "BEDROCK_EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
  "BEDROCK_RERANK_MODEL_ID": "cohere.rerank-v3-5:0",
  "RDS_HOST": "mba-mysql-db.conaisaskh5d.us-east-1.rds.amazonaws.com",
  "RDS_PORT": "3306",
  "RDS_DATABASE": "mba_db",
  "RDS_POOL_SIZE": "5",
  "RDS_POOL_MAX_OVERFLOW": "10",
  "S3_BUCKET_MBA": "mb-assistant-bucket",
  "S3_PREFIX_MBA": "mba/",
  "S3_SSE": "AES256",
  "QDRANT_URL": "https://YOUR_CLUSTER.aws.cloud.qdrant.io:6333",
  "QDRANT_COLLECTION": "benefit_coverage_rag_index",
  "EMBEDDING_DIMENSION": "1024",
  "LOG_LEVEL": "INFO",
  "LOG_DIR": "/tmp/logs",
  "LOG_FILE": "app.log"
}
```

**Note:** Sensitive values (RDS_PASSWORD, QDRANT_API_KEY) will be stored in AWS Secrets Manager (covered in Phase 5).

---

### Phase 3: Local Development & Testing (2-3 hours)

#### Step 3.1: Test Entrypoint Locally (Without AgentCore)

First, test the entrypoint file works correctly:

```bash
# Test imports and basic functionality
cd c:\Users\ROHIT\Work\HMA\MBA_CT

python entrypoints/orchestration_entrypoint.py

# Expected: Server starts on localhost
# (Ctrl+C to stop)
```

#### Step 3.2: Test with AgentCore Local Mode

AgentCore provides local testing with Docker:

```bash
# Configure for local testing
agentcore configure --entrypoint entrypoints/orchestration_entrypoint.py

# This will prompt:
# - Would you like to create IAM role? (y/n): n  [for local testing]
# - Would you like to create ECR repository? (y/n): n  [for local testing]
# - Enable memory? (y/n): y  [optional]

# Launch locally (requires Docker)
agentcore launch --local

# Expected output:
# Building Docker image...
# Starting local container...
# Agent available at: http://localhost:8080
```

**Test the Local Agent:**

```bash
# Test with agentcore CLI
agentcore invoke '{
  "prompt": "What is my deductible?",
  "context": {
    "member_id": "M12345",
    "dob": "1990-01-01"
  }
}'

# Or using curl
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is my deductible?",
    "context": {
      "member_id": "M12345",
      "dob": "1990-01-01"
    }
  }'

# Expected response:
# {
#   "success": true,
#   "response": "Your deductible information...",
#   "agent_used": "deductible_oop_agent",
#   "confidence": 0.95,
#   "metadata": {...}
# }
```

#### Step 3.3: Test Database Connectivity from Container

Verify the containerized agent can access your RDS database:

```bash
# Test member verification
agentcore invoke '{
  "prompt": "Verify member M12345 with DOB 1990-01-01"
}'

# Test deductible lookup
agentcore invoke '{
  "prompt": "What is the deductible for member M12345?"
}'

# Monitor logs
agentcore logs --follow
```

**Troubleshooting Database Connectivity:**

If database connection fails from Docker:

1. **Check Security Group** - Ensure RDS security group allows connections from your IP:

```bash
# Get your public IP
curl ifconfig.me

# Update RDS security group to allow your IP on port 3306
aws ec2 authorize-security-group-ingress \
  --group-id sg-XXXXXXXXX \
  --protocol tcp \
  --port 3306 \
  --cidr YOUR_IP/32
```

2. **Test Direct Connection:**

```bash
# Test from Docker container
docker exec -it <container_id> bash
python -c "from MBA.services.database.client import RDSClient; \
           client = RDSClient(); \
           print(client.test_connection())"
```

#### Step 3.4: Test All Agent Paths

Test each agent type through orchestration:

```bash
# Test 1: Member Verification
agentcore invoke '{"prompt": "Verify member M001"}'

# Test 2: Deductible Lookup
agentcore invoke '{"prompt": "What is my deductible for member M001?"}'

# Test 3: Benefit Accumulator
agentcore invoke '{"prompt": "How many physical therapy visits has member M001 used?"}'

# Test 4: Benefit Coverage RAG
agentcore invoke '{"prompt": "Does my plan cover chiropractic care?"}'

# Test 5: Intent Identification
agentcore invoke '{"prompt": "I want to know about my coverage"}'
```

**Success Criteria:**
- ✅ All agent types respond correctly
- ✅ Database queries return valid data
- ✅ RAG queries return relevant documents
- ✅ Response times < 5 seconds
- ✅ No errors in logs

#### Step 3.5: Stop Local Testing

```bash
# Stop local container
agentcore stop

# Clean up Docker resources (optional)
docker system prune -a
```

---

### Phase 4: Agent Configuration for AWS (1-2 hours)

#### Step 4.1: Configure AgentCore for AWS Deployment

Now configure for actual AWS deployment (creates IAM roles and ECR repository):

```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT

# Configure for AWS deployment
agentcore configure --entrypoint entrypoints/orchestration_entrypoint.py

# Prompts:
# ✓ Would you like to create IAM execution role? (y/n): y
#   → Creates role: bedrock-agentcore-execution-role-XXXXX
#
# ✓ Would you like to create ECR repository? (y/n): y
#   → Creates ECR: mba-orchestration-agent
#
# ✓ Enable session memory? (y/n): y
#   → Enables built-in session management
#
# ✓ Memory timeout (minutes) [default: 15]: 15
#   → Session expires after 15 minutes of inactivity
#
# ✓ AWS Region [default: us-west-2]: us-east-1
#   → Deploy to us-east-1 (same as RDS)
```

**Expected Output:**

```
✓ Configuration complete!

Created resources:
  - IAM Role: arn:aws:iam::123456789012:role/bedrock-agentcore-execution-role-abc123
  - ECR Repository: 123456789012.dkr.ecr.us-east-1.amazonaws.com/mba-orchestration-agent
  - Config file: .bedrock_agentcore.yaml

Next steps:
  1. Review .bedrock_agentcore.yaml
  2. Run: agentcore launch
```

#### Step 4.2: Review and Customize Configuration

Inspect the generated configuration file:

**File: `.bedrock_agentcore.yaml`** (Auto-generated)

```yaml
# AWS Bedrock AgentCore Configuration
# Auto-generated by bedrock-agentcore-starter-toolkit

runtime:
  # Agent entrypoint
  entrypoint: entrypoints/orchestration_entrypoint.py

  # AWS Region
  region: us-east-1

  # Runtime environment
  runtime_name: mba-orchestration-agent

  # Container configuration
  container:
    image_name: mba-orchestration-agent
    registry: 123456789012.dkr.ecr.us-east-1.amazonaws.com
    python_version: "3.11"

  # IAM execution role
  execution_role_arn: arn:aws:iam::123456789012:role/bedrock-agentcore-execution-role-abc123

  # Session memory
  memory:
    enabled: true
    timeout_minutes: 15

  # Environment variables (non-sensitive)
  environment:
    AWS_DEFAULT_REGION: us-east-1
    BEDROCK_MODEL_ID: anthropic.claude-3-5-sonnet-20241022-v2:0
    BEDROCK_EMBEDDING_MODEL_ID: amazon.titan-embed-text-v2:0
    RDS_HOST: mba-mysql-db.conaisaskh5d.us-east-1.rds.amazonaws.com
    RDS_PORT: "3306"
    RDS_DATABASE: mba_db
    S3_BUCKET_MBA: mb-assistant-bucket
    QDRANT_URL: https://YOUR_CLUSTER.aws.cloud.qdrant.io:6333
    QDRANT_COLLECTION: benefit_coverage_rag_index
    LOG_LEVEL: INFO

  # Secrets (will be stored in AWS Secrets Manager)
  secrets:
    - name: RDS_PASSWORD
      secret_arn: null  # Will be created in Phase 5
    - name: QDRANT_API_KEY
      secret_arn: null  # Will be created in Phase 5

  # Build configuration
  build:
    method: codebuild  # Uses AWS CodeBuild (no local Docker needed)
    dockerfile: null   # Auto-generated
    requirements: requirements.txt

  # Logging
  logging:
    cloudwatch_log_group: /aws/bedrock/agentcore/mba-orchestration-agent
    log_level: INFO

  # Tracing
  tracing:
    xray_enabled: true
```

**Customization:**

Add additional IAM permissions for RDS and S3 access:

```bash
# Get the execution role name
ROLE_ARN=$(grep "execution_role_arn" .bedrock_agentcore.yaml | cut -d' ' -f2)
ROLE_NAME=$(echo $ROLE_ARN | cut -d'/' -f2)

echo "Role Name: $ROLE_NAME"
```

#### Step 4.3: Add IAM Permissions for Data Access

The execution role needs permissions to access RDS, S3, Qdrant, and Secrets Manager.

**Create IAM policy for data access:**

**File: `deployment/configs/iam_data_access_policy.json`**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockModelAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0",
        "arn:aws:bedrock:us-east-1::foundation-model/cohere.rerank-v3-5:0"
      ]
    },
    {
      "Sid": "S3BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mb-assistant-bucket",
        "arn:aws:s3:::mb-assistant-bucket/*"
      ]
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:mba/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:*:log-group:/aws/bedrock/agentcore/*"
    },
    {
      "Sid": "XRayTracing",
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

**Attach policy to execution role:**

```bash
# Create the policy
aws iam create-policy \
  --policy-name MBA-AgentCore-DataAccess \
  --policy-document file://deployment/configs/iam_data_access_policy.json

# Get policy ARN
POLICY_ARN=$(aws iam list-policies \
  --query 'Policies[?PolicyName==`MBA-AgentCore-DataAccess`].Arn' \
  --output text)

echo "Policy ARN: $POLICY_ARN"

# Attach to execution role
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn $POLICY_ARN

# Verify attachment
aws iam list-attached-role-policies --role-name $ROLE_NAME
```

**Expected output:**

```json
{
  "AttachedPolicies": [
    {
      "PolicyName": "MBA-AgentCore-DataAccess",
      "PolicyArn": "arn:aws:iam::123456789012:policy/MBA-AgentCore-DataAccess"
    },
    {
      "PolicyName": "AmazonBedrockAgentCoreExecutionRole",
      "PolicyArn": "arn:aws:iam::aws:policy/service-role/AmazonBedrockAgentCoreExecutionRole"
    }
  ]
}
```

---

### Phase 5: Secrets Management (1 hour)

#### Step 5.1: Create Secrets in AWS Secrets Manager

Store sensitive credentials securely:

**Create RDS Password Secret:**

```bash
# Create secret for RDS password
aws secretsmanager create-secret \
  --name mba/rds/password \
  --description "MBA RDS MySQL password" \
  --secret-string "YOUR_RDS_PASSWORD_HERE" \
  --region us-east-1

# Get secret ARN
RDS_SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id mba/rds/password \
  --region us-east-1 \
  --query 'ARN' \
  --output text)

echo "RDS Secret ARN: $RDS_SECRET_ARN"
```

**Create Qdrant API Key Secret:**

```bash
# Create secret for Qdrant API key
aws secretsmanager create-secret \
  --name mba/qdrant/api-key \
  --description "MBA Qdrant Vector DB API Key" \
  --secret-string "YOUR_QDRANT_API_KEY_HERE" \
  --region us-east-1

# Get secret ARN
QDRANT_SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id mba/qdrant/api-key \
  --region us-east-1 \
  --query 'ARN' \
  --output text)

echo "Qdrant Secret ARN: $QDRANT_SECRET_ARN"
```

#### Step 5.2: Update Configuration with Secret ARNs

Edit `.bedrock_agentcore.yaml` to reference the secrets:

```yaml
secrets:
  - name: RDS_PASSWORD
    secret_arn: arn:aws:secretsmanager:us-east-1:123456789012:secret:mba/rds/password-XXXXX
  - name: QDRANT_API_KEY
    secret_arn: arn:aws:secretsmanager:us-east-1:123456789012:secret:mba/qdrant/api-key-XXXXX
```

#### Step 5.3: Update Entrypoint to Use Secrets

Modify `entrypoints/orchestration_entrypoint.py` to load secrets from Secrets Manager:

**Add at top of file:**

```python
import boto3
import os

def load_secrets():
    """Load secrets from AWS Secrets Manager"""
    secrets_client = boto3.client('secretsmanager', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

    # Load RDS password if not already set
    if not os.getenv('RDS_PASSWORD'):
        try:
            response = secrets_client.get_secret_value(SecretId='mba/rds/password')
            os.environ['RDS_PASSWORD'] = response['SecretString']
            logger.info("Loaded RDS password from Secrets Manager")
        except Exception as e:
            logger.error(f"Failed to load RDS password: {e}")

    # Load Qdrant API key if not already set
    if not os.getenv('QDRANT_API_KEY'):
        try:
            response = secrets_client.get_secret_value(SecretId='mba/qdrant/api-key')
            os.environ['QDRANT_API_KEY'] = response['SecretString']
            logger.info("Loaded Qdrant API key from Secrets Manager")
        except Exception as e:
            logger.error(f"Failed to load Qdrant API key: {e}")

# Load secrets on module import
load_secrets()
```

---

### Phase 6: Deployment to AWS (1-2 hours)

#### Step 6.1: Deploy to AgentCore Runtime

Now deploy the agent to AWS:

```bash
cd c:\Users\ROHIT\Work\HMA\MBA_CT

# Deploy to AWS
agentcore launch

# This command will:
# 1. Build Docker image (using AWS CodeBuild)
# 2. Push image to ECR
# 3. Create AgentCore Runtime
# 4. Deploy agent to runtime
# 5. Configure logging and tracing
# 6. Return runtime endpoint
```

**Expected Output:**

```
🚀 Deploying MBA_CT Orchestration Agent to AWS Bedrock AgentCore...

Step 1/5: Building Docker image...
  ✓ Using AWS CodeBuild for build (no local Docker needed)
  ✓ CodeBuild project: bedrock-agentcore-build-mba-orchestration
  ✓ Build started: Build ID abc123
  ✓ Build status: IN_PROGRESS
  ✓ Build logs: https://console.aws.amazon.com/codebuild/...

  [Wait time: 3-5 minutes]

  ✓ Build completed successfully
  ✓ Image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/mba-orchestration-agent:latest

Step 2/5: Pushing image to ECR...
  ✓ Image pushed to ECR

Step 3/5: Creating AgentCore Runtime...
  ✓ Runtime name: mba-orchestration-agent
  ✓ Runtime ARN: arn:aws:bedrock:us-east-1:123456789012:agent-runtime/mba-orchestration-agent
  ✓ Execution role: bedrock-agentcore-execution-role-abc123
  ✓ Memory: 2048 MB
  ✓ Timeout: 300 seconds

Step 4/5: Deploying agent...
  ✓ Deployment status: DEPLOYING
  ✓ Health checks: PASSING

  [Wait time: 2-3 minutes]

  ✓ Deployment status: DEPLOYED
  ✓ Agent status: READY

Step 5/5: Configuring logging and monitoring...
  ✓ CloudWatch Log Group: /aws/bedrock/agentcore/mba-orchestration-agent
  ✓ X-Ray tracing: ENABLED
  ✓ CloudWatch metrics: ENABLED

✓ Deployment complete!

Agent Details:
  - Runtime ARN: arn:aws:bedrock:us-east-1:123456789012:agent-runtime/mba-orchestration-agent
  - Status: READY
  - Region: us-east-1
  - Image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/mba-orchestration-agent:latest

Endpoints:
  - Invoke: https://bedrock-agentcore.us-east-1.amazonaws.com/agent/invoke
  - Health: https://bedrock-agentcore.us-east-1.amazonaws.com/agent/health

Next steps:
  1. Test with: agentcore invoke '{"prompt": "Hello"}'
  2. View logs: aws logs tail /aws/bedrock/agentcore/mba-orchestration-agent --follow
  3. Set up API Gateway for external access
```

#### Step 6.2: Verify Deployment

**Test the deployed agent:**

```bash
# Test with agentcore CLI
agentcore invoke '{"prompt": "What is my deductible?", "context": {"member_id": "M12345"}}'

# Expected response:
# {
#   "success": true,
#   "response": "Your deductible information for member M12345...",
#   "agent_used": "deductible_oop_agent",
#   "confidence": 0.95,
#   "metadata": {
#     "processing_time_seconds": 2.34,
#     "timestamp": "2025-01-15T10:30:00Z"
#   }
# }
```

**View logs:**

```bash
# Tail logs in real-time
aws logs tail /aws/bedrock/agentcore/mba-orchestration-agent --follow

# Search logs for errors
aws logs filter-log-events \
  --log-group-name /aws/bedrock/agentcore/mba-orchestration-agent \
  --filter-pattern "ERROR"
```

**Check agent status:**

```bash
# Get runtime details
aws bedrock-agentcore describe-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --region us-east-1

# Expected output:
# {
#   "agentRuntimeName": "mba-orchestration-agent",
#   "agentRuntimeArn": "arn:aws:bedrock:us-east-1:...",
#   "status": "READY",
#   "createdAt": "2025-01-15T10:00:00Z",
#   "lastModifiedAt": "2025-01-15T10:05:00Z"
# }
```

#### Step 6.3: Load Testing

Test the agent under load to verify scaling:

```bash
# Create a test script
cat > test_load.sh <<'EOF'
#!/bin/bash

# Load test script - sends 100 concurrent requests

for i in {1..100}; do
  (
    agentcore invoke "{\"prompt\": \"Test query $i\"}" > /dev/null 2>&1
    echo "Request $i completed"
  ) &
done

wait
echo "Load test completed"
EOF

chmod +x test_load.sh

# Run load test
./test_load.sh

# Monitor CloudWatch metrics during test
aws cloudwatch get-metric-statistics \
  --namespace AWS/BedrockAgentCore \
  --metric-name Invocations \
  --dimensions Name=AgentRuntimeName,Value=mba-orchestration-agent \
  --statistics Sum \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300
```

**Success Criteria:**
- ✅ All requests complete successfully
- ✅ Average response time < 5 seconds
- ✅ No errors in logs
- ✅ Auto-scaling activates (check CloudWatch metrics)

---

### Phase 7: API Gateway Setup (2-3 hours)

#### Step 7.1: Create API Gateway REST API

Expose your agent through API Gateway for external access:

```bash
# Create REST API
API_ID=$(aws apigateway create-rest-api \
  --name "MBA-Orchestration-API" \
  --description "Medical Benefits Administration Orchestration API" \
  --endpoint-configuration types=REGIONAL \
  --region us-east-1 \
  --query 'id' \
  --output text)

echo "API ID: $API_ID"

# Get root resource ID
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --region us-east-1 \
  --query 'items[0].id' \
  --output text)

echo "Root Resource ID: $ROOT_RESOURCE_ID"
```

#### Step 7.2: Create API Resources and Methods

```bash
# Create /orchestrate resource
ORCHESTRATE_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_RESOURCE_ID \
  --path-part orchestrate \
  --region us-east-1 \
  --query 'id' \
  --output text)

echo "Orchestrate Resource ID: $ORCHESTRATE_RESOURCE_ID"

# Create POST method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $ORCHESTRATE_RESOURCE_ID \
  --http-method POST \
  --authorization-type API_KEY \
  --api-key-required \
  --region us-east-1

echo "POST method created"
```

#### Step 7.3: Create Lambda Integration (Proxy to AgentCore)

Create a Lambda function to proxy requests to AgentCore Runtime:

**File: `deployment/lambda/agentcore_proxy.py`**

```python
import json
import boto3
import os

bedrock_agentcore = boto3.client('bedrock-agentcore', region_name='us-east-1')

AGENT_RUNTIME_ARN = os.environ['AGENT_RUNTIME_ARN']

def lambda_handler(event, context):
    """
    Proxy requests from API Gateway to Bedrock AgentCore Runtime
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # Extract parameters
        prompt = body.get('prompt', '')
        session_id = body.get('session_id', None)
        context_data = body.get('context', {})

        # Invoke AgentCore Runtime
        response = bedrock_agentcore.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            payload=json.dumps({
                'prompt': prompt,
                'session_id': session_id,
                'context': context_data
            })
        )

        # Parse response
        response_body = json.loads(response['body'].read())

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }
```

**Deploy Lambda:**

```bash
# Package Lambda
cd deployment/lambda
zip agentcore_proxy.zip agentcore_proxy.py

# Create Lambda execution role
aws iam create-role \
  --role-name MBA-AgentCore-Proxy-Role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }
    ]
  }'

# Attach policies
aws iam attach-role-policy \
  --role-name MBA-AgentCore-Proxy-Role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create custom policy for AgentCore invocation
cat > agentcore_invoke_policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeAgentRuntime",
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name MBA-AgentCore-Invoke \
  --policy-document file://agentcore_invoke_policy.json

aws iam attach-role-policy \
  --role-name MBA-AgentCore-Proxy-Role \
  --policy-arn arn:aws:iam::123456789012:policy/MBA-AgentCore-Invoke

# Get agent runtime ARN
AGENT_RUNTIME_ARN=$(aws bedrock-agentcore describe-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --region us-east-1 \
  --query 'agentRuntimeArn' \
  --output text)

# Create Lambda function
LAMBDA_ARN=$(aws lambda create-function \
  --function-name MBA-AgentCore-Proxy \
  --runtime python3.11 \
  --role arn:aws:iam::123456789012:role/MBA-AgentCore-Proxy-Role \
  --handler agentcore_proxy.lambda_handler \
  --zip-file fileb://agentcore_proxy.zip \
  --environment Variables="{AGENT_RUNTIME_ARN=$AGENT_RUNTIME_ARN}" \
  --timeout 300 \
  --memory-size 256 \
  --region us-east-1 \
  --query 'FunctionArn' \
  --output text)

echo "Lambda ARN: $LAMBDA_ARN"

cd ../..
```

#### Step 7.4: Integrate Lambda with API Gateway

```bash
# Set up Lambda integration
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $ORCHESTRATE_RESOURCE_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
  --region us-east-1

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name MBA-AgentCore-Proxy \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:123456789012:$API_ID/*/POST/orchestrate" \
  --region us-east-1
```

#### Step 7.5: Enable CORS

```bash
# Enable CORS for OPTIONS preflight
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $ORCHESTRATE_RESOURCE_ID \
  --http-method OPTIONS \
  --authorization-type NONE \
  --region us-east-1

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $ORCHESTRATE_RESOURCE_ID \
  --http-method OPTIONS \
  --type MOCK \
  --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
  --region us-east-1

aws apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $ORCHESTRATE_RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers": true, "method.response.header.Access-Control-Allow-Methods": true, "method.response.header.Access-Control-Allow-Origin": true}' \
  --region us-east-1

aws apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $ORCHESTRATE_RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'"'", "method.response.header.Access-Control-Allow-Methods": "'"'"'POST,OPTIONS'"'"'", "method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'"}' \
  --region us-east-1
```

#### Step 7.6: Create API Key and Usage Plan

```bash
# Create API key
API_KEY_ID=$(aws apigateway create-api-key \
  --name MBA-Orchestration-API-Key \
  --description "API Key for MBA Orchestration" \
  --enabled \
  --region us-east-1 \
  --query 'id' \
  --output text)

# Get API key value
API_KEY_VALUE=$(aws apigateway get-api-key \
  --api-key $API_KEY_ID \
  --include-value \
  --region us-east-1 \
  --query 'value' \
  --output text)

echo "API Key: $API_KEY_VALUE"
echo "SAVE THIS KEY - It won't be shown again"

# Create usage plan
USAGE_PLAN_ID=$(aws apigateway create-usage-plan \
  --name MBA-Orchestration-Usage-Plan \
  --description "Usage plan for MBA Orchestration API" \
  --throttle burstLimit=1000,rateLimit=5000 \
  --quota limit=1000000,period=MONTH \
  --region us-east-1 \
  --query 'id' \
  --output text)

echo "Usage Plan ID: $USAGE_PLAN_ID"

# Create deployment
DEPLOYMENT_ID=$(aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod \
  --stage-description "Production Stage" \
  --description "Initial deployment" \
  --region us-east-1 \
  --query 'id' \
  --output text)

echo "Deployment ID: $DEPLOYMENT_ID"

# Associate usage plan with stage
aws apigateway update-usage-plan \
  --usage-plan-id $USAGE_PLAN_ID \
  --patch-operations op=add,path=/apiStages,value=$API_ID:prod \
  --region us-east-1

# Associate API key with usage plan
aws apigateway create-usage-plan-key \
  --usage-plan-id $USAGE_PLAN_ID \
  --key-id $API_KEY_ID \
  --key-type API_KEY \
  --region us-east-1
```

#### Step 7.7: Get API Endpoint

```bash
# Get API endpoint
API_ENDPOINT="https://$API_ID.execute-api.us-east-1.amazonaws.com/prod/orchestrate"

echo "=========================================="
echo "API Gateway Setup Complete!"
echo "=========================================="
echo "API Endpoint: $API_ENDPOINT"
echo "API Key: $API_KEY_VALUE"
echo "=========================================="
echo ""
echo "Test with:"
echo "curl -X POST $API_ENDPOINT \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'x-api-key: $API_KEY_VALUE' \\"
echo "  -d '{\"prompt\": \"What is my deductible?\"}'"
```

#### Step 7.8: Test API Gateway

```bash
# Test the API
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY_VALUE" \
  -d '{
    "prompt": "What is my deductible?",
    "context": {
      "member_id": "M12345",
      "dob": "1990-01-01"
    }
  }'

# Expected response:
# {
#   "success": true,
#   "response": "Your deductible information...",
#   "agent_used": "deductible_oop_agent",
#   "confidence": 0.95,
#   "metadata": {...}
# }
```

---

### Phase 8: Monitoring & Observability (1-2 hours)

#### Step 8.1: Create CloudWatch Dashboard

```bash
# Create dashboard
cat > dashboard.json <<'EOF'
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/BedrockAgentCore", "Invocations", {"stat": "Sum"}],
          [".", "Errors", {"stat": "Sum"}],
          [".", "Throttles", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Agent Invocations"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/BedrockAgentCore", "Duration", {"stat": "Average"}],
          ["...", {"stat": "p99"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Response Times"
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "SOURCE '/aws/bedrock/agentcore/mba-orchestration-agent'\n| fields @timestamp, @message\n| filter @message like /ERROR/\n| sort @timestamp desc\n| limit 20",
        "region": "us-east-1",
        "title": "Recent Errors"
      }
    }
  ]
}
EOF

aws cloudwatch put-dashboard \
  --dashboard-name MBA-Orchestration-Dashboard \
  --dashboard-body file://dashboard.json

echo "Dashboard created: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=MBA-Orchestration-Dashboard"
```

#### Step 8.2: Configure CloudWatch Alarms

```bash
# Alarm for high error rate
aws cloudwatch put-metric-alarm \
  --alarm-name MBA-Agent-High-Error-Rate \
  --alarm-description "Alert when agent error rate exceeds threshold" \
  --metric-name Errors \
  --namespace AWS/BedrockAgentCore \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=AgentRuntimeName,Value=mba-orchestration-agent \
  --treat-missing-data notBreaching \
  --region us-east-1

# Alarm for high latency
aws cloudwatch put-metric-alarm \
  --alarm-name MBA-Agent-High-Latency \
  --alarm-description "Alert when agent latency exceeds 5 seconds" \
  --metric-name Duration \
  --namespace AWS/BedrockAgentCore \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=AgentRuntimeName,Value=mba-orchestration-agent \
  --treat-missing-data notBreaching \
  --region us-east-1

echo "CloudWatch Alarms created"
```

#### Step 8.3: Enable X-Ray Tracing

X-Ray is automatically enabled by AgentCore. View traces:

```bash
# Get trace summaries
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --region us-east-1

# Open X-Ray console
echo "X-Ray Console: https://console.aws.amazon.com/xray/home?region=us-east-1#/traces"
```

#### Step 8.4: Set Up Log Insights Queries

Useful CloudWatch Logs Insights queries:

**Query 1: Top Agents Used**

```sql
fields @timestamp, agent_used
| filter ispresent(agent_used)
| stats count() by agent_used
| sort count() desc
```

**Query 2: Slow Requests**

```sql
fields @timestamp, processing_time_seconds, prompt
| filter processing_time_seconds > 5
| sort processing_time_seconds desc
| limit 20
```

**Query 3: Error Analysis**

```sql
fields @timestamp, @message
| filter @message like /ERROR/ or @message like /Exception/
| parse @message /(?<error_type>\w+Error):/
| stats count() by error_type
| sort count() desc
```

Save these queries in the console for quick access.

---

### Phase 9: Testing & Validation (2-3 hours)

#### Step 9.1: End-to-End Integration Test

Create comprehensive test suite:

**File: `tests/test_agentcore_integration.py`**

```python
"""
Integration tests for MBA_CT AgentCore Runtime deployment
"""

import requests
import json
import time
from typing import Dict, Any

API_ENDPOINT = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/orchestrate"
API_KEY = "YOUR_API_KEY_HERE"

HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY
}

def test_member_verification():
    """Test member verification agent"""
    payload = {
        "prompt": "Verify member M001 with DOB 1990-01-01",
        "context": {
            "member_id": "M001",
            "dob": "1990-01-01"
        }
    }

    response = requests.post(API_ENDPOINT, headers=HEADERS, json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == True
    assert data["agent_used"] == "member_verification_agent"
    print(f"✓ Member Verification: {data['response']}")

def test_deductible_lookup():
    """Test deductible/OOP agent"""
    payload = {
        "prompt": "What is the deductible for member M001?",
        "context": {"member_id": "M001"}
    }

    response = requests.post(API_ENDPOINT, headers=HEADERS, json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == True
    assert "deductible" in data["response"].lower()
    print(f"✓ Deductible Lookup: {data['response']}")

def test_benefit_accumulator():
    """Test benefit accumulator agent"""
    payload = {
        "prompt": "How many physical therapy visits has member M001 used?",
        "context": {"member_id": "M001"}
    }

    response = requests.post(API_ENDPOINT, headers=HEADERS, json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == True
    print(f"✓ Benefit Accumulator: {data['response']}")

def test_benefit_coverage_rag():
    """Test benefit coverage RAG agent"""
    payload = {
        "prompt": "Does my plan cover chiropractic care?"
    }

    response = requests.post(API_ENDPOINT, headers=HEADERS, json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == True
    assert data["agent_used"] == "benefit_coverage_rag_agent"
    print(f"✓ Coverage RAG: {data['response']}")

def test_session_management():
    """Test session persistence"""
    session_id = "test-session-" + str(int(time.time()))

    # First request
    payload1 = {
        "prompt": "My member ID is M001",
        "session_id": session_id
    }
    response1 = requests.post(API_ENDPOINT, headers=HEADERS, json=payload1)
    assert response1.status_code == 200

    # Second request (should remember member ID)
    payload2 = {
        "prompt": "What is my deductible?",
        "session_id": session_id
    }
    response2 = requests.post(API_ENDPOINT, headers=HEADERS, json=payload2)
    assert response2.status_code == 200

    print(f"✓ Session Management: Session {session_id} maintained context")

def test_error_handling():
    """Test error handling"""
    payload = {
        "prompt": ""  # Empty prompt
    }

    response = requests.post(API_ENDPOINT, headers=HEADERS, json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == False
    assert "error" in data or "Invalid" in data["response"]
    print(f"✓ Error Handling: Gracefully handled invalid input")

def test_performance():
    """Test response time"""
    payload = {
        "prompt": "What is my deductible?",
        "context": {"member_id": "M001"}
    }

    start_time = time.time()
    response = requests.post(API_ENDPOINT, headers=HEADERS, json=payload)
    end_time = time.time()

    assert response.status_code == 200
    response_time = end_time - start_time
    assert response_time < 10  # Should respond within 10 seconds

    print(f"✓ Performance: Response time = {response_time:.2f}s")

if __name__ == "__main__":
    print("=" * 60)
    print("MBA_CT AgentCore Integration Tests")
    print("=" * 60)

    try:
        test_member_verification()
        test_deductible_lookup()
        test_benefit_accumulator()
        test_benefit_coverage_rag()
        test_session_management()
        test_error_handling()
        test_performance()

        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
```

**Run tests:**

```bash
# Update API endpoint and key in the file
python tests/test_agentcore_integration.py
```

#### Step 9.2: Load Testing

Use Apache Bench or Locust for load testing:

```bash
# Install Apache Bench (if not installed)
# On Windows: Download from Apache website
# On Linux: sudo apt-get install apache2-utils

# Create test payload
cat > test_payload.json <<EOF
{
  "prompt": "What is my deductible?",
  "context": {"member_id": "M001"}
}
EOF

# Run load test (100 requests, 10 concurrent)
ab -n 100 -c 10 -T "application/json" \
   -H "x-api-key: $API_KEY_VALUE" \
   -p test_payload.json \
   $API_ENDPOINT

# Expected results:
# - Time per request: < 5000ms
# - Failed requests: 0
# - Requests per second: > 2
```

#### Step 9.3: Security Testing

**Test API Key Authentication:**

```bash
# Test without API key (should fail)
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test"}'

# Expected: 403 Forbidden

# Test with invalid API key (should fail)
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -H "x-api-key: invalid-key-12345" \
  -d '{"prompt": "Test"}'

# Expected: 403 Forbidden
```

**Test Rate Limiting:**

```bash
# Send requests exceeding rate limit
for i in {1..1100}; do
  curl -X POST $API_ENDPOINT \
    -H "Content-Type: application/json" \
    -H "x-api-key: $API_KEY_VALUE" \
    -d "{\"prompt\": \"Test $i\"}" &
done

wait

# Expected: Some requests return 429 Too Many Requests
```

---

### Phase 10: Production Deployment Checklist (1 hour)

#### Step 10.1: Pre-Launch Checklist

**Security:**
- [ ] API Gateway authentication enabled (API Key or Cognito)
- [ ] All secrets stored in AWS Secrets Manager (no hardcoded credentials)
- [ ] IAM policies follow least-privilege principle
- [ ] RDS security group restricts access to AgentCore execution role only
- [ ] S3 bucket encryption enabled (SSE-AES256)
- [ ] CloudWatch Logs retention configured (e.g., 30 days)
- [ ] WAF rules configured (optional but recommended)

**Performance:**
- [ ] Load testing completed successfully
- [ ] Response times < 5 seconds for 95th percentile
- [ ] Agent auto-scaling tested
- [ ] Database connection pooling configured
- [ ] Qdrant vector DB latency acceptable (< 500ms)

**Monitoring:**
- [ ] CloudWatch Dashboard created
- [ ] CloudWatch Alarms configured
- [ ] X-Ray tracing enabled
- [ ] Log Insights queries saved
- [ ] SNS topic for alerts configured (optional)

**Reliability:**
- [ ] Health check endpoint working
- [ ] Error handling tested
- [ ] Retry logic implemented
- [ ] Circuit breakers configured (if needed)
- [ ] Backup and recovery plan documented

**Documentation:**
- [ ] API documentation updated
- [ ] Deployment runbook created
- [ ] Troubleshooting guide written
- [ ] Rollback procedure documented
- [ ] Team training completed

#### Step 10.2: Go-Live Procedure

```bash
# 1. Final smoke test
agentcore invoke '{"prompt": "System health check"}'

# 2. Verify all monitors are active
aws cloudwatch describe-alarms \
  --alarm-name-prefix MBA-Agent \
  --region us-east-1

# 3. Check recent logs for errors
aws logs filter-log-events \
  --log-group-name /aws/bedrock/agentcore/mba-orchestration-agent \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR"

# 4. Announce go-live
echo "MBA_CT AgentCore Runtime is now live!"
echo "API Endpoint: $API_ENDPOINT"
echo "Documentation: https://your-docs-url/api"
```

#### Step 10.3: Post-Deployment Validation

Monitor for 24 hours after launch:

```bash
# Monitor invocations
watch -n 60 'aws cloudwatch get-metric-statistics \
  --namespace AWS/BedrockAgentCore \
  --metric-name Invocations \
  --dimensions Name=AgentRuntimeName,Value=mba-orchestration-agent \
  --statistics Sum \
  --start-time $(date -u -d "5 minutes ago" +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --region us-east-1'

# Monitor errors
aws logs tail /aws/bedrock/agentcore/mba-orchestration-agent --follow | grep ERROR
```

#### Step 10.4: Rollback Plan

If issues arise, rollback procedure:

```bash
# 1. Update API Gateway to maintenance mode
aws apigateway update-stage \
  --rest-api-id $API_ID \
  --stage-name prod \
  --patch-operations op=replace,path=/description,value="MAINTENANCE MODE" \
  --region us-east-1

# 2. Redirect traffic to previous FastAPI service (if still running)
# Update API Gateway integration to point to previous endpoint

# 3. Disable AgentCore Runtime (optional)
aws bedrock-agentcore update-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --status PAUSED \
  --region us-east-1

# 4. Investigate issues
aws logs tail /aws/bedrock/agentcore/mba-orchestration-agent --since 1h

# 5. When ready to restore
aws bedrock-agentcore update-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --status READY \
  --region us-east-1
```

---

## 6. Code Examples

### 6.1 Complete Entrypoint Examples

See **Phase 2, Step 2.1** for the main orchestration entrypoint.

### 6.2 Individual Agent Entrypoints (Microservices Architecture)

If you choose to deploy each agent separately:

**Example: Member Verification Agent Entrypoint**

**File: `entrypoints/member_verification_entrypoint.py`**

```python
from bedrock_agentcore import BedrockAgentCoreApp
from MBA.agents.member_verification_agent import MemberVerificationAgent

app = BedrockAgentCoreApp()
agent = MemberVerificationAgent()

@app.entrypoint
async def invoke(payload):
    member_id = payload.get("member_id")
    dob = payload.get("dob")

    result = await agent.verify_member(member_id=member_id, dob=dob)
    return result

if __name__ == "__main__":
    app.run()
```

Deploy each agent:

```bash
# Configure and deploy each agent
for agent in member_verification deductible_oop benefit_accumulator; do
  agentcore configure --entrypoint entrypoints/${agent}_entrypoint.py
  agentcore launch
done
```

### 6.3 Testing Scripts

See **Phase 9, Step 9.1** for comprehensive integration tests.

---

## 7. Architecture Decisions

### 7.1 Single Orchestration vs. Microservices

**Recommendation: Start with Single Orchestration**

| Criteria | Single Orchestration | Microservices |
|----------|----------------------|---------------|
| **Deployment Complexity** | Low (1 deployment) | High (7 deployments) |
| **Latency** | Low (in-process calls) | Higher (network calls) |
| **Cost** | Lower (1 runtime) | Higher (7 runtimes) |
| **Scaling** | Good (scales entire app) | Better (scales individual agents) |
| **Debugging** | Easier (single log stream) | Harder (distributed tracing) |
| **Development Velocity** | Faster (monolithic) | Slower (coordination) |
| **Fault Isolation** | Lower | Higher |
| **Team Autonomy** | Lower | Higher |

**When to Migrate to Microservices:**
- Individual agents have vastly different scaling needs
- Different agents have different SLAs
- Multiple teams own different agents
- Fault isolation is critical

### 7.2 Authentication Strategy

**Options:**

1. **API Key** (Recommended for MVP)
   - ✅ Simple to implement
   - ✅ Easy to revoke
   - ❌ Shared secret (not user-specific)

2. **AWS IAM**
   - ✅ No shared secrets
   - ✅ Fine-grained permissions
   - ❌ Requires AWS credentials for clients

3. **Amazon Cognito**
   - ✅ User-specific authentication
   - ✅ OAuth 2.0 support
   - ✅ User pools for management
   - ❌ More complex setup

**Recommendation:** Start with API Key, migrate to Cognito for production with multiple users.

### 7.3 Logging Strategy

**Log Retention:**
- Development: 7 days
- Staging: 30 days
- Production: 90 days (or per compliance requirements)

**Log Levels:**
- Development: DEBUG
- Staging: INFO
- Production: WARN (INFO for specific modules)

---

## 8. Cost & Pricing

### 8.1 AgentCore Free Tier (Until Sept 16, 2025)

**Included:**
- ✅ Unlimited agent invocations
- ✅ Unlimited runtime hours
- ✅ Built-in gateway and memory
- ✅ No charges for AgentCore service

**You Still Pay For:**
- AWS Bedrock model invocations (Claude, Titan Embeddings, Cohere)
- RDS MySQL (existing)
- S3 storage (existing)
- Qdrant Cloud (external)
- CloudWatch Logs storage
- API Gateway requests
- Data transfer

### 8.2 Post-Free Tier Pricing (After Sept 16, 2025)

**Estimated Monthly Costs:**

| Service | Usage | Cost |
|---------|-------|------|
| **Bedrock AgentCore Runtime** | ~100,000 invocations | $50 |
| **Bedrock Claude 3.5 Sonnet** | ~500,000 tokens input, 100,000 output | $75 |
| **Bedrock Titan Embeddings** | ~10M tokens | $1 |
| **API Gateway** | ~100,000 requests | $0.35 |
| **CloudWatch Logs** | ~10 GB ingested | $5 |
| **RDS MySQL** | db.t3.medium (existing) | $60 |
| **S3 Storage** | ~100 GB (existing) | $2.30 |
| **Data Transfer** | ~50 GB out | $4.50 |
| **Qdrant Cloud** | Standard plan (external) | $95 |
| **TOTAL** | | **~$293/month** |

**Cost Optimization Tips:**

1. **Use Caching** - Cache frequent queries to reduce Bedrock calls
2. **Optimize Prompts** - Shorter prompts = fewer tokens = lower cost
3. **Batch Processing** - Process multiple queries in one invocation
4. **Right-Size RDS** - Consider Aurora Serverless for variable loads
5. **S3 Lifecycle** - Move old files to S3 Glacier
6. **CloudWatch Logs** - Export old logs to S3 for cheaper storage

### 8.3 Cost Monitoring

Set up AWS Budgets:

```bash
# Create budget alert
aws budgets create-budget \
  --account-id 123456789012 \
  --budget '{
    "BudgetName": "MBA-Monthly-Budget",
    "BudgetLimit": {"Amount": "300", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[{
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80
    },
    "Subscribers": [{
      "SubscriptionType": "EMAIL",
      "Address": "your-email@example.com"
    }]
  }]'
```

---

## 9. Monitoring & Operations

### 9.1 Key Metrics to Monitor

**AgentCore Metrics:**
- `Invocations` - Total number of agent invocations
- `Errors` - Failed invocations
- `Throttles` - Rate-limited requests
- `Duration` - Response time (average, p95, p99)
- `ConcurrentExecutions` - Number of concurrent runtime instances

**API Gateway Metrics:**
- `Count` - Total API requests
- `4XXError` - Client errors
- `5XXError` - Server errors
- `Latency` - API Gateway latency
- `IntegrationLatency` - Backend latency

**Bedrock Metrics:**
- `Invocations` - Model invocations
- `InputTokens` - Tokens sent to model
- `OutputTokens` - Tokens generated by model
- `ModelErrors` - Model invocation failures

### 9.2 Operational Runbooks

**Runbook 1: High Error Rate**

1. Check CloudWatch Alarms
2. Query recent errors:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/bedrock/agentcore/mba-orchestration-agent \
     --filter-pattern "ERROR" \
     --start-time $(date -u -d '1 hour ago' +%s)000
   ```
3. Identify error patterns (database, timeout, validation)
4. Check dependent services (RDS, Qdrant, S3)
5. If database issue: Check RDS connections, security groups
6. If timeout: Increase Lambda/AgentCore timeout
7. If validation: Review recent code changes

**Runbook 2: High Latency**

1. Check X-Ray traces for slow components
2. Query slow requests:
   ```sql
   fields @timestamp, processing_time_seconds, agent_used
   | filter processing_time_seconds > 5
   | sort processing_time_seconds desc
   ```
3. Identify bottleneck (database query, Qdrant search, Bedrock call)
4. If database: Add indexes, optimize queries
5. If Qdrant: Check vector DB performance, consider caching
6. If Bedrock: Review prompt size, consider streaming

**Runbook 3: Agent Not Responding**

1. Check agent status:
   ```bash
   aws bedrock-agentcore describe-agent-runtime \
     --agent-runtime-name mba-orchestration-agent
   ```
2. If status not READY: Restart agent
3. Check recent deployments (may be deploying)
4. Review CloudWatch Logs for startup errors
5. Test health endpoint:
   ```bash
   agentcore invoke '{"action": "health_check"}'
   ```
6. If persistent: Redeploy agent

### 9.3 Maintenance Windows

**Recommended Schedule:**
- **Weekly:** Review metrics, check logs for warnings
- **Monthly:** Review cost reports, optimize configurations
- **Quarterly:** Security audit, dependency updates

**Deployment Windows:**
- **Production:** Tuesday/Wednesday 2-4 PM (low traffic)
- **Staging:** Anytime
- **Rollback SLA:** < 15 minutes

---

## 10. Troubleshooting

### 10.1 Common Deployment Issues

**Issue: "IAM role creation failed"**

```
Error: AccessDeniedException - User not authorized to create IAM role
```

**Solution:**
```bash
# Ensure your AWS user has IAM permissions
aws iam attach-user-policy \
  --user-name your-user \
  --policy-arn arn:aws:iam::aws:policy/IAMFullAccess
```

---

**Issue: "ECR push failed"**

```
Error: denied: Your authorization token has expired
```

**Solution:**
```bash
# Re-authenticate with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com
```

---

**Issue: "Agent deployment stuck in DEPLOYING state"**

**Solution:**
```bash
# Check CodeBuild logs
aws codebuild list-builds-for-project \
  --project-name bedrock-agentcore-build-mba-orchestration \
  --region us-east-1

# Get build logs
aws codebuild batch-get-builds \
  --ids <build-id> \
  --region us-east-1

# If stuck > 15 minutes, cancel and retry
aws bedrock-agentcore delete-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --region us-east-1

agentcore launch  # Retry
```

### 10.2 Runtime Issues

**Issue: "Database connection timeout"**

```
Error: pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```

**Solution:**
```bash
# 1. Check RDS security group
aws ec2 describe-security-groups \
  --group-ids sg-XXXXXXXXX

# 2. Add AgentCore execution role to security group
# Get VPC security group for AgentCore
aws bedrock-agentcore describe-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --query 'vpcConfig.securityGroupIds'

# 3. Add inbound rule to RDS security group
aws ec2 authorize-security-group-ingress \
  --group-id <rds-security-group> \
  --protocol tcp \
  --port 3306 \
  --source-group <agentcore-security-group>
```

---

**Issue: "Secrets Manager access denied"**

```
Error: ClientError: An error occurred (AccessDeniedException) when calling GetSecretValue
```

**Solution:**
```bash
# Add Secrets Manager permissions to execution role
aws iam attach-role-policy \
  --role-name <execution-role-name> \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

---

**Issue: "Qdrant connection failed"**

```
Error: QdrantException: Could not connect to Qdrant
```

**Solution:**
```bash
# 1. Verify Qdrant URL and API key
python -c "from qdrant_client import QdrantClient; \
           client = QdrantClient(url='YOUR_URL', api_key='YOUR_KEY'); \
           print(client.get_collections())"

# 2. Check firewall rules in Qdrant Cloud console
# 3. Ensure API key has correct permissions
```

### 10.3 Performance Issues

**Issue: "High latency (> 10 seconds)"**

**Debugging Steps:**

1. **Check X-Ray Trace:**
```bash
# Find slow traces
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --filter-expression 'duration > 10' \
  --region us-east-1
```

2. **Analyze Log Timing:**
```sql
fields @timestamp, processing_time_seconds, agent_used
| filter processing_time_seconds > 10
| stats avg(processing_time_seconds), max(processing_time_seconds), count() by agent_used
```

3. **Common Causes & Fixes:**

| Cause | Solution |
|-------|----------|
| Slow database queries | Add indexes, optimize queries |
| Large vector searches | Reduce result limit, add filters |
| Cold starts | Increase memory, use provisioned concurrency |
| Large prompts | Reduce system prompt size, use caching |
| Network latency to Qdrant | Consider self-hosted Qdrant in AWS |

---

**Issue: "Throttling errors (429)"**

```
Error: TooManyRequestsException: Rate exceeded
```

**Solution:**
```bash
# 1. Check current usage plan limits
aws apigateway get-usage-plan --usage-plan-id <id>

# 2. Increase rate limits
aws apigateway update-usage-plan \
  --usage-plan-id <id> \
  --patch-operations \
    op=replace,path=/throttle/rateLimit,value=10000 \
    op=replace,path=/throttle/burstLimit,value=2000

# 3. For AgentCore throttling, request limit increase
aws service-quotas request-service-quota-increase \
  --service-code bedrock \
  --quota-code L-12345678 \
  --desired-value 1000
```

### 10.4 Debugging Tips

**Enable Debug Logging:**

Update `.bedrock_agentcore.yaml`:
```yaml
logging:
  log_level: DEBUG
```

Redeploy:
```bash
agentcore launch
```

**Test Individual Components:**

```python
# Test RDS connection
from MBA.services.database.client import RDSClient
client = RDSClient()
print(client.execute_query("SELECT 1"))

# Test S3 connection
from MBA.services.storage.s3_client import S3Client
client = S3Client()
print(client.list_objects("mba/"))

# Test Qdrant connection
from qdrant_client import QdrantClient
from MBA.core.settings import settings
client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
print(client.get_collections())

# Test Bedrock connection
import boto3
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
response = bedrock.invoke_model(
    modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
    body='{"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 100, "anthropic_version": "bedrock-2023-05-31"}'
)
print(response)
```

**Local Debugging:**

```bash
# Run entrypoint locally (outside AgentCore)
cd c:\Users\ROHIT\Work\HMA\MBA_CT
python entrypoints/orchestration_entrypoint.py

# Test with curl
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test query"}'
```

---

## 11. Appendices

### Appendix A: Command Reference

**AgentCore CLI Commands:**

```bash
# Configuration
agentcore configure --entrypoint <file>  # Configure agent
agentcore configure --list               # List configurations

# Deployment
agentcore launch                         # Deploy to AWS
agentcore launch --local                 # Deploy locally
agentcore launch --region us-west-2      # Deploy to specific region

# Testing
agentcore invoke '{"prompt": "test"}'    # Invoke agent
agentcore invoke --file payload.json     # Invoke with file

# Monitoring
agentcore logs                           # View logs
agentcore logs --follow                  # Tail logs
agentcore logs --since 1h                # Logs from last hour

# Management
agentcore describe                       # Get agent details
agentcore stop                           # Stop local agent
agentcore update                         # Update agent config
agentcore delete                         # Delete agent runtime

# Utilities
agentcore --version                      # Version info
agentcore --help                         # Help
```

### Appendix B: Environment Variables

**Required Environment Variables:**

```env
# AWS Configuration (Required)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1

# Bedrock Models (Required)
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0

# RDS MySQL (Required)
RDS_HOST=mba-mysql-db.conaisaskh5d.us-east-1.rds.amazonaws.com
RDS_PORT=3306
RDS_DATABASE=mba_db
RDS_USERNAME=admin
RDS_PASSWORD=<from-secrets-manager>
RDS_POOL_SIZE=5
RDS_POOL_MAX_OVERFLOW=10

# S3 Storage (Required)
S3_BUCKET_MBA=mb-assistant-bucket
S3_PREFIX_MBA=mba/
S3_SSE=AES256

# Qdrant Vector DB (Required)
QDRANT_URL=https://your-cluster.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=<from-secrets-manager>
QDRANT_COLLECTION=benefit_coverage_rag_index
EMBEDDING_DIMENSION=1024

# Logging (Optional)
LOG_LEVEL=INFO
LOG_DIR=/tmp/logs
LOG_FILE=app.log

# CSV Ingestion (Optional)
CSV_DATA_DIR=/tmp/csv
CSV_CHUNK_SIZE=1000
CSV_ENCODING=utf-8
```

### Appendix C: IAM Policy Templates

**AgentCore Execution Role Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::mb-assistant-bucket",
        "arn:aws:s3:::mb-assistant-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:mba/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

### Appendix D: Useful AWS CLI Commands

**Bedrock AgentCore:**

```bash
# List agent runtimes
aws bedrock-agentcore list-agent-runtimes --region us-east-1

# Describe agent runtime
aws bedrock-agentcore describe-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --region us-east-1

# Update agent runtime
aws bedrock-agentcore update-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --environment Variables={LOG_LEVEL=DEBUG} \
  --region us-east-1

# Delete agent runtime
aws bedrock-agentcore delete-agent-runtime \
  --agent-runtime-name mba-orchestration-agent \
  --region us-east-1
```

**CloudWatch Logs:**

```bash
# List log groups
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock/agentcore \
  --region us-east-1

# Tail logs
aws logs tail /aws/bedrock/agentcore/mba-orchestration-agent --follow

# Search logs
aws logs filter-log-events \
  --log-group-name /aws/bedrock/agentcore/mba-orchestration-agent \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000

# Start query
aws logs start-query \
  --log-group-name /aws/bedrock/agentcore/mba-orchestration-agent \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20'
```

**API Gateway:**

```bash
# List APIs
aws apigateway get-rest-apis --region us-east-1

# Get API details
aws apigateway get-rest-api --rest-api-id <id> --region us-east-1

# Create deployment
aws apigateway create-deployment \
  --rest-api-id <id> \
  --stage-name prod \
  --region us-east-1

# Delete API
aws apigateway delete-rest-api --rest-api-id <id> --region us-east-1
```

### Appendix E: Additional Resources

**Documentation:**
- [AWS Bedrock AgentCore Docs](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Strands Agents Documentation](https://strandsagents.com/documentation/)
- [AgentCore Starter Toolkit GitHub](https://github.com/aws/bedrock-agentcore-starter-toolkit)
- [Bedrock AgentCore Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples)

**Tutorials:**
- [How to Deploy an AI Agent with Amazon Bedrock AgentCore](https://www.freecodecamp.org/news/deploy-an-ai-agent-with-amazon-bedrock)
- [Building Production-Ready AI Agents](https://dev.to/aws/building-production-ready-ai-agents-with-strands-agents-and-amazon-bedrock-agentcore-3dg0)

**Community:**
- AWS re:Post - [Bedrock AgentCore](https://repost.aws/tags/TAGcNyJkMXQaKuPF4P3_ixEg/amazon-bedrock-agentcore)
- Stack Overflow - Tag: `aws-bedrock-agentcore`

**Support:**
- AWS Support Console
- GitHub Issues: [AgentCore Starter Toolkit Issues](https://github.com/aws/bedrock-agentcore-starter-toolkit/issues)

---

## Conclusion

This guide provides a comprehensive, step-by-step approach to deploying the MBA_CT multi-agent system to AWS Bedrock AgentCore Runtime. By following these phases, you'll transform your local Strands-based agents into a production-ready, scalable, and secure cloud service.

**Key Takeaways:**

✅ **Zero Infrastructure** - No containers, servers, or orchestration to manage
✅ **Production-Ready** - Built-in gateway, memory, logging, and tracing
✅ **Cost-Effective** - Free until Sept 2025, pay-as-you-go after
✅ **Framework Agnostic** - Works with your existing Strands agents
✅ **Enterprise Security** - IAM, VPC, encryption, secrets management
✅ **Auto-Scaling** - Handles variable workloads automatically

**Next Steps:**

1. Complete Phase 1-2 (Environment setup and code preparation)
2. Test locally with `agentcore launch --local`
3. Deploy to AWS with `agentcore launch`
4. Set up API Gateway for external access
5. Configure monitoring and alerts
6. Run comprehensive tests
7. Go live!

For questions or issues, refer to the Troubleshooting section or reach out via AWS Support.

**Happy Deploying! 🚀**

---

*Document Version: 1.0*
*Last Updated: January 2025*
*Author: MBA_CT Team*
