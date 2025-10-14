# Member Verification Agent

AWS Bedrock-powered member identity verification system using Strands agent orchestration.

## Overview

The Member Verification Agent authenticates member identities by querying the RDS MySQL `memberdata` table using flexible criteria combinations. It integrates AWS Bedrock language models with database operations for secure member verification.

## Architecture

```
User Request → Strands Agent → Bedrock LLM → verify_member Tool → RDS MySQL
                                                                    ↓
JSON Response ← Response Formatting ← Tool Result ← SQL Query Result
```

## Components

- **agent.py**: Strands agent initialization with Bedrock client
- **tools.py**: Member verification tool with database integration
- **wrapper.py**: High-level async interface for verification workflows
- **prompt.py**: System prompt for agent behavior
- **api.py**: FastAPI endpoints for HTTP access
- **test_agent.py**: Test script for validation

## Setup

### Prerequisites

```bash
# Install dependencies
uv pip install -e .

# Or using pip
pip install -e .
```

### Environment Configuration

Create `.env` file:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# RDS Configuration
RDS_HOST=your-rds-endpoint.amazonaws.com
RDS_PORT=3306
RDS_DATABASE=mba_db
RDS_USERNAME=admin
RDS_PASSWORD=your_password
```

## Usage

### Direct Agent Usage

```python
from MBA.agents import MemberVerificationAgent

agent = MemberVerificationAgent()

# Single verification
result = await agent.verify_member(
    member_id="M12345",
    dob="1990-01-01"
)

# Batch verification
results = await agent.verify_member_batch([
    {"member_id": "M001", "dob": "1990-01-01"},
    {"member_id": "M002", "name": "John Doe"}
])
```

### API Usage

Start the API server:

```bash
cd src/MBA/agents
python api.py
```

API will be available at `http://localhost:8001`

#### Verify Single Member

```bash
curl -X POST "http://localhost:8001/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "M12345",
    "dob": "1990-01-01"
  }'
```

#### Verify Multiple Members

```bash
curl -X POST "http://localhost:8001/verify/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "members": [
      {"member_id": "M001", "dob": "1990-01-01"},
      {"member_id": "M002", "name": "John Doe"}
    ]
  }'
```

## Testing

### Run Test Script

```bash
cd src/MBA/agents
python test_agent.py
```

### Manual Testing

```python
import asyncio
from MBA.agents import MemberVerificationAgent

async def test():
    agent = MemberVerificationAgent()
    
    # Test valid member
    result = await agent.verify_member(member_id="M12345", dob="1990-01-01")
    print(result)
    
    # Test invalid member
    result = await agent.verify_member(member_id="INVALID")
    print(result)

asyncio.run(test())
```

## Response Format

### Success Response

```json
{
  "valid": true,
  "member_id": "M12345",
  "name": "John Doe",
  "dob": "1990-01-01"
}
```

### Failure Response

```json
{
  "valid": false,
  "message": "Authentication failed"
}
```

### Error Response

```json
{
  "error": "Verification failed: Database error"
}
```

## Database Schema

The `memberdata` table must contain:

- `member_id`: VARCHAR (primary identifier)
- `first_name`: VARCHAR
- `last_name`: VARCHAR  
- `dob`: DATE

## Verification Logic

The agent supports flexible verification using:

1. **Member ID**: Exact match on `member_id` field
2. **Date of Birth**: Exact match on `dob` field
3. **Name**: Fuzzy match on concatenated `first_name + last_name` or individual name parts

Multiple parameters use AND logic for stricter validation.

## Error Handling

- **Missing Parameters**: Returns validation error
- **Database Errors**: Logs error, returns generic failure message
- **Connection Issues**: Automatic retry with exponential backoff
- **Invalid Credentials**: Configuration error with detailed logging

## Logging

All operations are logged with structured context:

- Verification requests and results
- Database connection status
- Error conditions with stack traces
- Performance metrics

Logs are written to `logs/app.log` and console output.

## Security

- SQL injection prevention via parameterized queries
- Credential management through environment variables
- No sensitive data in log outputs
- Secure database connections with SSL

## Performance

- Connection pooling for database efficiency
- Lazy agent initialization for fast cold starts
- Batch processing for multiple verifications
- Async/await for non-blocking operations

## Troubleshooting

### Agent Won't Initialize

Check AWS credentials and Bedrock service availability:

```bash
aws bedrock list-foundation-models --region us-east-1
```

### Database Connection Fails

Verify RDS endpoint and credentials:

```bash
mysql -h your-rds-endpoint.amazonaws.com -u admin -p mba_db
```

### Import Errors

Ensure all dependencies are installed:

```bash
uv pip install strands-agents sqlalchemy boto3
```

## API Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`