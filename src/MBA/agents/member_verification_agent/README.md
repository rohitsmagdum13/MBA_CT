# Member Verification Agent

## Overview

The **Member Verification Agent** is an AWS Bedrock-powered AI agent that validates member identities by querying the RDS MySQL database. It uses flexible authentication criteria including member ID, date of birth, and name to verify member eligibility and enrollment status.

**Agent Type**: Database Query Agent
**Technology Stack**: AWS Bedrock (Claude Sonnet 4.5), Strands Framework, SQLAlchemy, MySQL
**Purpose**: Member identity verification and eligibility checking

---

## Table of Contents

- [Architecture](#architecture)
- [Workflow Diagram](#workflow-diagram)
- [File Structure](#file-structure)
- [Component Details](#component-details)
- [Usage Examples](#usage-examples)
- [Database Schema](#database-schema)
- [Error Handling](#error-handling)
- [Testing](#testing)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Member Verification Agent                     │
│                                                                  │
│  ┌────────────┐    ┌─────────────┐    ┌──────────────────┐    │
│  │  wrapper.py│───▶│  agent.py   │───▶│  AWS Bedrock     │    │
│  │  (Public   │    │  (Strands   │    │  Claude Sonnet   │    │
│  │   API)     │    │   Agent)    │    │      4.5         │    │
│  └────────────┘    └─────────────┘    └──────────────────┘    │
│         │                  │                     │              │
│         │                  ▼                     ▼              │
│         │           ┌─────────────┐      ┌─────────────┐       │
│         │           │  prompt.py  │      │  tools.py   │       │
│         │           │  (System    │      │  (@tool     │       │
│         │           │   Prompt)   │      │  decorator) │       │
│         │           └─────────────┘      └─────────────┘       │
│         │                                        │              │
│         └────────────────────────────────────────┼──────────────┤
│                                                  ▼              │
│                                         ┌─────────────────┐    │
│                                         │   RDS MySQL     │    │
│                                         │  (memberdata)   │    │
│                                         └─────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **wrapper.py**: High-level interface for member verification
2. **agent.py**: Strands agent initialization with Bedrock
3. **tools.py**: Database query tool with @tool decorator
4. **prompt.py**: System prompt defining agent behavior
5. **__init__.py**: Package exports

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       MEMBER VERIFICATION WORKFLOW                       │
└─────────────────────────────────────────────────────────────────────────┘

User Request
    │
    ▼
┌────────────────────────────────────────┐
│  wrapper.verify_member()               │
│  - Accepts member_id, dob, name        │
│  - Validates parameters                │
│  - Lazy initializes agent              │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│  WORKAROUND: Direct Tool Call          │
│  (Bypasses Strands agent due to        │
│   AgentResult limitation)              │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│  tools.verify_member()                 │
│  - Build dynamic SQL query             │
│  - Execute against memberdata table    │
│  - Process results                     │
└────────────────────────────────────────┘
    │
    ├──▶ Build Query
    │   ┌─────────────────────────────────────┐
    │   │  _build_verification_query()        │
    │   │  - Extract parameters               │
    │   │  - Construct WHERE conditions       │
    │   │  - Build SQL with parameterization  │
    │   └─────────────────────────────────────┘
    │
    ├──▶ Execute Query
    │   ┌─────────────────────────────────────┐
    │   │  Database Connection                │
    │   │  - Connect to RDS MySQL             │
    │   │  - Execute parameterized query      │
    │   │  - Fetch single result              │
    │   └─────────────────────────────────────┘
    │
    └──▶ Process Result
        ┌─────────────────────────────────────┐
        │  Result Formatting                  │
        │  - Extract member data              │
        │  - Format dates                     │
        │  - Return structured JSON           │
        └─────────────────────────────────────┘
        │
        ▼
    ┌────────────────────────────────────┐
    │  Return to User                    │
    │  {"valid": true, "member_id": ...} │
    └────────────────────────────────────┘
```

---

## File Structure

```
member_verification_agent/
│
├── __init__.py              # Package exports and public API
│   └── Exports: MemberVerificationAgent, verification_agent
│
├── wrapper.py               # High-level wrapper class (PRIMARY INTERFACE)
│   ├── MemberVerificationAgent (class)
│   │   ├── __init__()                    # Initialize with lazy loading
│   │   ├── _ensure_initialized()         # Lazy load Strands agent
│   │   ├── verify_member()               # Main verification method (ASYNC)
│   │   └── verify_member_batch()         # Batch verification (ASYNC)
│
├── agent.py                 # Strands agent initialization
│   ├── _setup_aws_credentials()          # Configure Bedrock access
│   └── verification_agent                # Strands Agent instance
│
├── tools.py                 # Database query tools
│   ├── _build_verification_query()       # SQL query builder
│   └── verify_member() [@tool]           # Main verification tool (ASYNC)
│
├── prompt.py                # System prompt for AI agent
│   └── VERIFICATION_PROMPT               # Instructions for Claude
│
└── README.md                # This file
```

---

## Component Details

### 1. wrapper.py - MemberVerificationAgent Class

**Purpose**: Provides a production-grade Python interface for member verification.

#### Class: `MemberVerificationAgent`

```python
class MemberVerificationAgent:
    """
    Production wrapper for AWS Bedrock-powered member verification agent.

    Attributes:
        _agent: Underlying Strands Agent instance
        _initialized: Initialization state flag
    """
```

#### Method: `verify_member()`

**Signature:**
```python
async def verify_member(
    self,
    member_id: Optional[str] = None,
    dob: Optional[str] = None,
    name: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters:**
- `member_id` (str, optional): Member identifier (e.g., "M1001")
- `dob` (str, optional): Date of birth in YYYY-MM-DD format
- `name` (str, optional): Full name for secondary validation

**Returns:**
```python
# Success
{
    "valid": True,
    "member_id": "M1001",
    "name": "John Doe",
    "dob": "1990-01-01"
}

# Failure
{
    "valid": False,
    "message": "Authentication failed"
}

# Error
{
    "error": "Verification failed: Database error"
}
```

**Implementation Details:**

1. **Parameter Validation**
   ```python
   # At least one parameter required
   if not any([member_id, dob, name]):
       raise ValueError("At least one verification parameter required")
   ```

2. **Lazy Initialization**
   ```python
   # Agent initialized only on first use
   self._ensure_initialized()
   ```

3. **Direct Tool Call (WORKAROUND)**
   ```python
   # Due to Strands AgentResult not capturing tool results properly,
   # we directly call the tool function instead of going through the LLM
   from .tools import verify_member as tool_func
   result = await tool_func(params)
   ```

4. **Error Handling**
   - Database errors: Caught and returned as `{"error": "..."}`
   - Configuration errors: Returned as service unavailable
   - All exceptions logged with context

---

### 2. tools.py - Database Query Tools

**Purpose**: Provides @tool decorated functions for database verification.

#### Function: `_build_verification_query()`

**Signature:**
```python
def _build_verification_query(params: Dict[str, Any]) -> tuple[Optional[str], Dict[str, Any]]
```

**Purpose**: Constructs dynamic SQL query based on provided parameters.

**Logic Flow:**
```
Input params: {member_id: "M1001", dob: "1990-01-01"}
    │
    ├─▶ Check member_id
    │   ├─ Present? Add: "member_id = :member_id"
    │   └─ Add to sql_params: {"member_id": "M1001"}
    │
    ├─▶ Check dob
    │   ├─ Present? Add: "dob = :dob"
    │   └─ Add to sql_params: {"dob": "1990-01-01"}
    │
    ├─▶ Check name
    │   ├─ Present? Add: "(CONCAT(first_name, ' ', last_name) = :name ...)"
    │   └─ Parse name into first_name, last_name
    │
    └─▶ Combine with AND logic
        └─ Result: "WHERE member_id = :member_id AND dob = :dob"
```

**Example:**
```python
# Input
params = {"member_id": "M1001", "dob": "1990-01-01"}

# Output
query = """
    SELECT
        member_id,
        CONCAT(first_name, ' ', last_name) AS name,
        dob
    FROM memberdata
    WHERE member_id = :member_id AND dob = :dob
    LIMIT 1
"""
sql_params = {"member_id": "M1001", "dob": "1990-01-01"}
```

**Security Features:**
- ✅ Parameterized queries (SQL injection prevention)
- ✅ Input sanitization (.strip())
- ✅ Type validation (isinstance checks)
- ✅ Limit 1 (prevents excessive results)

---

#### Function: `verify_member()` [@tool decorator]

**Signature:**
```python
@tool
async def verify_member(params: Dict[str, Any]) -> Dict[str, Any]
```

**Purpose**: Main verification tool that executes database query.

**Execution Flow:**
```
1. Import database connector
   └─ from ...etl.db import connect

2. Build verification query
   └─ query_sql, sql_params = _build_verification_query(params)

3. Validate parameters
   └─ if query_sql is None: return error

4. Execute database query
   ├─ with connect() as conn:
   ├─     result = conn.execute(text(query_sql), sql_params).fetchone()
   └─ Handle connection errors

5. Process results
   ├─ if result: Extract member_id, name, dob
   └─ else: Return {"valid": False}

6. Return structured response
   └─ {"valid": True/False, ...}
```

**Database Query Example:**
```sql
-- Generated query
SELECT
    member_id,
    CONCAT(first_name, ' ', last_name) AS name,
    dob
FROM memberdata
WHERE member_id = :member_id AND dob = :dob
LIMIT 1

-- Executed with parameters
:member_id = "M1001"
:dob = "1990-01-01"
```

**Error Handling:**
```python
try:
    # Query execution
    result = conn.execute(...)
except SQLAlchemyError as e:
    # Database-specific errors
    return {"error": "Verification failed: Database error"}
except Exception as e:
    # Unexpected errors
    return {"error": f"Verification failed: {str(e)}"}
```

---

### 3. agent.py - Strands Agent Initialization

**Purpose**: Initializes the Strands Agent with AWS Bedrock.

#### Function: `_setup_aws_credentials()`

**Logic:**
```python
if running_in_lambda:
    # Use execution role
    return {'region_name': settings.aws_default_region}
else:
    # Use explicit credentials
    os.environ['AWS_ACCESS_KEY_ID'] = settings.aws_access_key_id
    os.environ['AWS_SECRET_ACCESS_KEY'] = settings.aws_secret_access_key
    os.environ['AWS_DEFAULT_REGION'] = settings.aws_default_region

    return {
        'region_name': settings.aws_default_region,
        'aws_access_key_id': settings.aws_access_key_id,
        'aws_secret_access_key': settings.aws_secret_access_key
    }
```

#### Agent Initialization

```python
verification_agent = Agent(
    name="MemberVerificationAgent",
    system_prompt=VERIFICATION_PROMPT,
    tools=[verify_member],
    model=settings.bedrock_model_id  # e.g., "us.anthropic.claude-sonnet-4-5-v2:0"
)
```

**Components:**
- **name**: Agent identifier for logging
- **system_prompt**: Instructions from prompt.py
- **tools**: List of @tool decorated functions
- **model**: Bedrock model ID

---

### 4. prompt.py - System Prompt

**Purpose**: Defines the AI agent's behavior and capabilities.

**Structure:**
```
VERIFICATION_PROMPT = """
1. Role Definition
   - Who you are
   - What you do

2. Your Capabilities
   - Single verification
   - Batch verification
   - Flexible criteria

3. Verification Workflow
   - Step-by-step process
   - Tool usage
   - Response formatting

4. Decision-Making Guidelines
   - Parameter priority
   - Error handling
   - Edge cases

5. Response Format
   - Success response
   - Failure response
   - Error response

6. Examples
   - Example 1: Member ID + DOB
   - Example 2: Member ID only
   - Example 3: Invalid member
"""
```

**Key Instructions:**
- Always use the `verify_member` tool
- Return structured JSON responses
- Handle missing parameters gracefully
- Log all verification attempts

---

## Usage Examples

### Example 1: Verify by Member ID Only

```python
from src.MBA.agents.member_verification_agent import MemberVerificationAgent

agent = MemberVerificationAgent()

# Async usage
result = await agent.verify_member(member_id="M1001")

print(result)
# Output:
# {
#     "valid": True,
#     "member_id": "M1001",
#     "name": "Brandi Kim",
#     "dob": "2005-05-23"
# }
```

---

### Example 2: Verify by Member ID + DOB (Multi-Factor)

```python
result = await agent.verify_member(
    member_id="M1001",
    dob="2005-05-23"
)

print(result)
# Output:
# {
#     "valid": True,
#     "member_id": "M1001",
#     "name": "Brandi Kim",
#     "dob": "2005-05-23"
# }
```

---

### Example 3: Verify by DOB + Name

```python
result = await agent.verify_member(
    dob="2005-05-23",
    name="Brandi Kim"
)

print(result)
# Output:
# {
#     "valid": True,
#     "member_id": "M1001",
#     "name": "Brandi Kim",
#     "dob": "2005-05-23"
# }
```

---

### Example 4: Invalid Member (No Match)

```python
result = await agent.verify_member(member_id="M9999")

print(result)
# Output:
# {
#     "valid": False,
#     "message": "Authentication failed"
# }
```

---

### Example 5: Batch Verification

```python
members = [
    {"member_id": "M1001"},
    {"member_id": "M1002", "dob": "1961-04-08"},
    {"member_id": "M9999"}  # Invalid
]

results = await agent.verify_member_batch(members)

print(results)
# Output:
# [
#     {"valid": True, "member_id": "M1001", ...},
#     {"valid": True, "member_id": "M1002", ...},
#     {"valid": False, "message": "Authentication failed"}
# ]
```

---

## Database Schema

### Table: `memberdata`

```sql
CREATE TABLE memberdata (
    member_id VARCHAR(50) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE NOT NULL,
    -- Other fields...
);
```

**Required Fields:**
- `member_id`: Unique member identifier
- `first_name`: Member's first name
- `last_name`: Member's last name
- `dob`: Date of birth

**Sample Data:**
```
member_id | first_name | last_name | dob
----------|------------|-----------|------------
M1001     | Brandi     | Kim       | 2005-05-23
M1002     | Dawn       | Brown     | 1961-04-08
M1003     | Kathleen   | Clark     | 1964-04-13
```

---

## Error Handling

### Error Types and Responses

#### 1. Missing Parameters
```python
# No parameters provided
result = await agent.verify_member()
# Raises: ValueError("At least one verification parameter required")
```

#### 2. Database Connection Error
```python
# Database unavailable
result = await agent.verify_member(member_id="M1001")
# Returns: {"error": "Verification service unavailable: ..."}
```

#### 3. Database Query Error
```python
# SQLAlchemyError during query
result = await agent.verify_member(member_id="M1001")
# Returns: {"error": "Verification failed: Database error"}
```

#### 4. Member Not Found
```python
# No matching record
result = await agent.verify_member(member_id="M9999")
# Returns: {"valid": False, "message": "Authentication failed"}
```

---

## Testing

### Unit Tests

```python
import pytest
from src.MBA.agents.member_verification_agent import MemberVerificationAgent

@pytest.mark.asyncio
async def test_verify_valid_member():
    agent = MemberVerificationAgent()
    result = await agent.verify_member(member_id="M1001")

    assert result["valid"] == True
    assert result["member_id"] == "M1001"
    assert "name" in result
    assert "dob" in result

@pytest.mark.asyncio
async def test_verify_invalid_member():
    agent = MemberVerificationAgent()
    result = await agent.verify_member(member_id="M9999")

    assert result["valid"] == False
    assert "message" in result

@pytest.mark.asyncio
async def test_verify_missing_params():
    agent = MemberVerificationAgent()

    with pytest.raises(ValueError):
        await agent.verify_member()
```

### Integration Tests

```bash
# Test via API
curl -X POST "http://localhost:8000/member/verify" \
  -H "Content-Type: application/json" \
  -d '{"member_id": "M1001"}'

# Expected response:
# {
#   "valid": true,
#   "member_id": "M1001",
#   "name": "Brandi Kim",
#   "dob": "2005-05-23"
# }
```

---

## Performance Considerations

### Lazy Initialization
```python
# Agent initialized only on first use
agent = MemberVerificationAgent()  # Fast - no Bedrock connection
result = await agent.verify_member(...)  # First call initializes agent
```

### Database Connection Pooling
- SQLAlchemy handles connection pooling automatically
- Connections released after each query
- No persistent connections maintained

### Query Optimization
- `LIMIT 1` prevents excessive data retrieval
- Indexed columns (member_id, dob) for fast lookups
- Parameterized queries for query plan caching

---

## Security Features

### SQL Injection Prevention
✅ Parameterized queries using SQLAlchemy `text()` with bound parameters
✅ No string concatenation for SQL construction
✅ Input sanitization with `.strip()`

### Access Control
✅ AWS IAM roles for Bedrock access
✅ Database credentials from secure configuration
✅ No credentials in code

### Data Protection
✅ Structured logging without sensitive data
✅ Error messages don't expose internal details
✅ HTTPS for Bedrock communication

---

## Troubleshooting

### Issue: "Verification service unavailable"
**Cause**: Database connection failed
**Solution**: Check database credentials, network connectivity, RDS status

### Issue: "At least one identifier required"
**Cause**: No parameters provided
**Solution**: Pass at least one of: member_id, dob, or name

### Issue: Agent initialization fails
**Cause**: AWS credentials invalid
**Solution**: Check AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY in .env

### Issue: Slow verification
**Cause**: Database table not indexed
**Solution**: Add indexes on member_id, dob columns

---

## Dependencies

```python
# Core dependencies
strands>=1.0.0           # Agent framework
boto3>=1.26.0            # AWS SDK
sqlalchemy>=2.0.0        # Database ORM
pymysql>=1.0.0           # MySQL driver

# Internal dependencies
src.MBA.core.logging_config  # Logging setup
src.MBA.core.settings        # Configuration
src.MBA.core.exceptions      # Custom exceptions
src.MBA.etl.db              # Database connection
```

---

## Related Documentation

- [Orchestration Agent README](../orchestration_agent/README.md)
- [Deductible/OOP Agent README](../deductible_oop_agent/README.md)
- [Database ETL Documentation](../../etl/README.md)
- [API Documentation](../../microservices/README.md)

---

## Changelog

### v1.0.0 (Initial Release)
- ✅ AWS Bedrock integration with Claude Sonnet 4.5
- ✅ Flexible multi-parameter verification
- ✅ Batch verification support
- ✅ Comprehensive error handling
- ✅ Lazy initialization pattern
- ✅ Direct tool call workaround for Strands limitation

---

## License

Copyright © 2025 MBA System. All rights reserved.
