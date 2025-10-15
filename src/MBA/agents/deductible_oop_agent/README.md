# Deductible/OOP Agent

## Overview

The **Deductible/OOP Agent** is an AWS Bedrock-powered AI agent that retrieves member deductible and out-of-pocket (OOP) maximum information from the RDS MySQL database. It provides comprehensive cost-sharing details across multiple plan types (Individual/Family) and network levels (PPO, PAR, OON).

**Agent Type**: Database Query Agent
**Technology Stack**: AWS Bedrock (Claude Sonnet 4.5), Strands Framework, SQLAlchemy, MySQL
**Purpose**: Deductible and OOP limit lookups with met amounts and remaining balances

---

## Table of Contents

- [Architecture](#architecture)
- [Workflow Diagram](#workflow-diagram)
- [File Structure](#file-structure)
- [Component Details](#component-details)
- [Usage Examples](#usage-examples)
- [Database Schema](#database-schema)
- [Data Structure](#data-structure)
- [Error Handling](#error-handling)
- [Testing](#testing)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Deductible/OOP Agent                             │
│                                                                       │
│  ┌────────────┐    ┌─────────────┐    ┌──────────────────┐         │
│  │  wrapper.py│───▶│  agent.py   │───▶│  AWS Bedrock     │         │
│  │  (Public   │    │  (Strands   │    │  Claude Sonnet   │         │
│  │   API)     │    │   Agent)    │    │      4.5         │         │
│  └────────────┘    └─────────────┘    └──────────────────┘         │
│         │                  │                     │                   │
│         │                  ▼                     ▼                   │
│         │           ┌─────────────┐      ┌─────────────┐            │
│         │           │  prompt.py  │      │  tools.py   │            │
│         │           │  (System    │      │  (@tool     │            │
│         │           │   Prompt)   │      │  decorator) │            │
│         │           └─────────────┘      └─────────────┘            │
│         │                                        │                   │
│         └────────────────────────────────────────┼───────────────────┤
│                                                  ▼                   │
│                                         ┌──────────────────┐        │
│                                         │   RDS MySQL      │        │
│                                         │ (deductibles_oop)│        │
│                                         │  Transposed      │        │
│                                         │    Format        │        │
│                                         └──────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **wrapper.py**: High-level interface for deductible/OOP lookups
2. **agent.py**: Strands agent initialization with Bedrock
3. **tools.py**: Database query tool with data parsing logic
4. **prompt.py**: System prompt defining agent behavior
5. **__init__.py**: Package exports

---

## Workflow Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                    DEDUCTIBLE/OOP LOOKUP WORKFLOW                       │
└────────────────────────────────────────────────────────────────────────┘

User Request
    │
    ▼
┌────────────────────────────────────────┐
│  wrapper.get_deductible_oop()          │
│  - Accepts member_id                   │
│  - Validates parameter                 │
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
│  tools.get_deductible_oop()            │
│  - Validate member_id                  │
│  - Build transposed query              │
│  - Execute against database            │
│  - Parse results                       │
└────────────────────────────────────────┘
    │
    ├──▶ Build Query
    │   ┌──────────────────────────────────────┐
    │   │  SELECT Metric, `{member_id}` as     │
    │   │  value FROM deductibles_oop          │
    │   │  WHERE `{member_id}` IS NOT NULL     │
    │   └──────────────────────────────────────┘
    │
    ├──▶ Execute Query
    │   ┌──────────────────────────────────────┐
    │   │  Database Connection                 │
    │   │  - Connect to RDS MySQL              │
    │   │  - Execute query                     │
    │   │  - Fetch all metric rows             │
    │   └──────────────────────────────────────┘
    │
    └──▶ Parse Results
        ┌──────────────────────────────────────┐
        │  _parse_deductible_oop_results()     │
        │  - Convert flat metrics to structure │
        │  - Organize by plan type             │
        │  - Organize by network level         │
        │  - Calculate remaining amounts       │
        └──────────────────────────────────────┘
        │
        ▼
    ┌─────────────────────────────────────────┐
    │  Return Structured Data                 │
    │  {                                      │
    │    "found": true,                       │
    │    "member_id": "M1001",                │
    │    "individual": {                      │
    │      "ppo": {                           │
    │        "deductible": 2683,              │
    │        "deductible_met": 1840,          │
    │        "deductible_remaining": 843,     │
    │        "oop": 1120, ...                 │
    │      }                                  │
    │    },                                   │
    │    "family": {...}                      │
    │  }                                      │
    └─────────────────────────────────────────┘
```

---

## File Structure

```
deductible_oop_agent/
│
├── __init__.py              # Package exports
│   └── Exports: DeductibleOOPAgent, deductible_oop_agent
│
├── wrapper.py               # High-level wrapper class (PRIMARY INTERFACE)
│   ├── DeductibleOOPAgent (class)
│   │   ├── __init__()                      # Initialize with lazy loading
│   │   ├── _ensure_initialized()           # Lazy load Strands agent
│   │   ├── get_deductible_oop()            # Main lookup method (ASYNC)
│   │   └── get_deductible_oop_batch()      # Batch lookup (ASYNC)
│
├── agent.py                 # Strands agent initialization
│   ├── _setup_aws_credentials()            # Configure Bedrock access
│   └── deductible_oop_agent                # Strands Agent instance
│
├── tools.py                 # Database query tools
│   ├── _parse_deductible_oop_results()     # Parse transposed data
│   └── get_deductible_oop() [@tool]        # Main lookup tool (ASYNC)
│
├── prompt.py                # System prompt for AI agent
│   └── DEDUCTIBLE_OOP_PROMPT               # Instructions for Claude
│
└── README.md                # This file
```

---

## Component Details

### 1. wrapper.py - DeductibleOOPAgent Class

**Purpose**: Provides a production-grade Python interface for deductible/OOP lookups.

#### Class: `DeductibleOOPAgent`

```python
class DeductibleOOPAgent:
    """
    Production wrapper for AWS Bedrock-powered deductible/OOP agent.

    Attributes:
        _agent: Underlying Strands Agent instance
        _initialized: Initialization state flag
    """
```

#### Method: `get_deductible_oop()`

**Signature:**
```python
async def get_deductible_oop(
    self,
    member_id: str
) -> Dict[str, Any]
```

**Parameters:**
- `member_id` (str, required): Member identifier (e.g., "M1001")

**Returns:**
```python
# Success
{
    "found": True,
    "member_id": "M1001",
    "individual": {
        "ppo": {
            "deductible": 2683,
            "deductible_met": 1840,
            "deductible_remaining": 843,
            "oop": 1120,
            "oop_met": 495,
            "oop_remaining": 625
        },
        "par": {...},
        "oon": {...}
    },
    "family": {
        "ppo": {...},
        "par": {...},
        "oon": {...}
    }
}

# Not found
{
    "found": False,
    "message": "No deductible/OOP data found for member M9999"
}

# Error
{
    "error": "Lookup failed: Database error"
}
```

**Implementation Flow:**
```
1. Validate member_id parameter
   └─ if not member_id: raise ValueError

2. Lazy initialize agent
   └─ self._ensure_initialized()

3. Call tool directly (WORKAROUND)
   ├─ from .tools import get_deductible_oop as tool_func
   └─ result = await tool_func({"member_id": member_id})

4. Return structured response
```

---

### 2. tools.py - Database Query Tools

**Purpose**: Provides @tool decorated functions for database lookups with data parsing.

#### Function: `_parse_deductible_oop_results()`

**Signature:**
```python
def _parse_deductible_oop_results(member_id: str, results: List[tuple]) -> Dict[str, Any]
```

**Purpose**: Transforms flat database rows into hierarchical structure.

**Input Format (from database):**
```python
results = [
    ("Deductible IND PPO", 2683),
    ("Deductible IND PPO met", 1840),
    ("Deductible IND PPO Remaining", 843),
    ("OOP IND PPO", 1120),
    ("OOP IND PPO met", 495),
    ("OOP IND PPO Remaining", 625),
    ("Deductible IND PAR", 3000),
    # ... more rows
]
```

**Parsing Logic:**
```
Step 1: Convert to dictionary
    ├─ {"Deductible IND PPO": 2683, ...}

Step 2: Parse Individual Plans
    ├─ For network in ["PPO", "PAR", "OON"]:
    │   ├─ Extract deductible: metrics_dict.get(f"Deductible IND {network}")
    │   ├─ Extract deductible_met: metrics_dict.get(f"Deductible IND {network} met")
    │   ├─ Extract deductible_remaining: metrics_dict.get(f"Deductible IND {network} Remaining")
    │   ├─ Extract oop: metrics_dict.get(f"OOP IND {network}")
    │   ├─ Extract oop_met: metrics_dict.get(f"OOP IND {network} met")
    │   └─ Extract oop_remaining: metrics_dict.get(f"OOP IND {network} Remaining")

Step 3: Parse Family Plans
    └─ Same logic for FAM instead of IND

Step 4: Return structured data
```

**Output Format:**
```python
{
    "member_id": "M1001",
    "individual": {
        "ppo": {
            "deductible": 2683,
            "deductible_met": 1840,
            "deductible_remaining": 843,
            "oop": 1120,
            "oop_met": 495,
            "oop_remaining": 625
        },
        "par": {...},
        "oon": {...}
    },
    "family": {
        "ppo": {...},
        "par": {...},
        "oon": {...}
    }
}
```

---

#### Function: `get_deductible_oop()` [@tool decorator]

**Signature:**
```python
@tool
async def get_deductible_oop(params: Dict[str, Any]) -> Dict[str, Any]
```

**Purpose**: Main lookup tool that executes database query.

**Database Query:**
```sql
-- The table is in TRANSPOSED format with members as columns
SELECT Metric, `M1001` as value
FROM deductibles_oop
WHERE `M1001` IS NOT NULL

-- Returns rows like:
-- Metric                          | value
-- --------------------------------|-------
-- Deductible IND PPO              | 2683
-- Deductible IND PPO met          | 1840
-- Deductible IND PPO Remaining    | 843
-- OOP IND PPO                     | 1120
-- ...
```

**Execution Flow:**
```
1. Validate member_id
   ├─ member_id = params.get("member_id")
   ├─ if not member_id: return {"found": False}
   └─ member_id = str(member_id).strip()

2. Import database connector
   └─ from ...etl.db import connect

3. Build query for transposed table
   ├─ query = f"SELECT Metric, `{member_id}` as value"
   ├─         f"FROM deductibles_oop"
   └─         f"WHERE `{member_id}` IS NOT NULL"

4. Execute query
   ├─ with connect() as conn:
   └─     results = conn.execute(text(query)).fetchall()

5. Parse results
   ├─ if results:
   │   ├─ data = _parse_deductible_oop_results(member_id, results)
   │   └─ data["found"] = True
   └─ else:
       └─ return {"found": False, "message": "No data found"}

6. Return structured response
```

**Error Handling:**
```python
try:
    # Query execution
    results = conn.execute(...)
except SQLAlchemyError as e:
    # Database-specific errors
    return {"error": "Lookup failed: Database error"}
except Exception as e:
    # Unexpected errors
    return {"error": f"Lookup failed: {str(e)}"}
```

---

### 3. agent.py - Strands Agent Initialization

**Purpose**: Initializes the Strands Agent with AWS Bedrock.

```python
deductible_oop_agent = Agent(
    name="DeductibleOOPAgent",
    system_prompt=DEDUCTIBLE_OOP_PROMPT,
    tools=[get_deductible_oop],
    model=settings.bedrock_model_id
)
```

---

### 4. prompt.py - System Prompt

**Purpose**: Defines the AI agent's behavior and capabilities.

**Key Instructions:**
- Always use the `get_deductible_oop` tool
- Return structured JSON responses
- Explain deductible vs OOP differences
- Handle missing data gracefully
- Provide remaining balance calculations

---

## Usage Examples

### Example 1: Get All Deductible/OOP Data

```python
from src.MBA.agents.deductible_oop_agent import DeductibleOOPAgent

agent = DeductibleOOPAgent()

# Async usage
result = await agent.get_deductible_oop(member_id="M1001")

print(result)
# Output:
# {
#     "found": True,
#     "member_id": "M1001",
#     "individual": {
#         "ppo": {
#             "deductible": 2683,
#             "deductible_met": 1840,
#             "deductible_remaining": 843,
#             "oop": 1120,
#             "oop_met": 495,
#             "oop_remaining": 625
#         },
#         "par": {...},
#         "oon": {...}
#     },
#     "family": {...}
# }
```

---

### Example 2: Member Not Found

```python
result = await agent.get_deductible_oop(member_id="M9999")

print(result)
# Output:
# {
#     "found": False,
#     "message": "No deductible/OOP data found for member M9999"
# }
```

---

### Example 3: Batch Lookup

```python
member_ids = ["M1001", "M1002", "M1003"]

results = await agent.get_deductible_oop_batch(member_ids)

print(results)
# Output:
# [
#     {"found": True, "member_id": "M1001", ...},
#     {"found": True, "member_id": "M1002", ...},
#     {"found": True, "member_id": "M1003", ...}
# ]
```

---

### Example 4: Extract Specific Network

```python
result = await agent.get_deductible_oop(member_id="M1001")

# Access PPO individual deductible
ppo_deductible = result["individual"]["ppo"]["deductible"]
print(f"PPO Deductible: ${ppo_deductible}")

# Access remaining OOP
ppo_oop_remaining = result["individual"]["ppo"]["oop_remaining"]
print(f"OOP Remaining: ${ppo_oop_remaining}")
```

---

## Database Schema

### Table: `deductibles_oop` (Transposed Format)

**⚠️ IMPORTANT**: This table uses a **transposed format** where members are columns, not rows!

```sql
-- Transposed structure
CREATE TABLE deductibles_oop (
    Metric VARCHAR(100) PRIMARY KEY,
    M1001 INTEGER,
    M1002 INTEGER,
    M1003 INTEGER,
    -- ... one column per member
);
```

**Sample Data:**
```
Metric                          | M1001 | M1002 | M1003
--------------------------------|-------|-------|-------
Deductible IND PPO              | 2683  | 3000  | 2500
Deductible IND PPO met          | 1840  | 1500  | 2000
Deductible IND PPO Remaining    | 843   | 1500  | 500
OOP IND PPO                     | 1120  | 5000  | 6000
OOP IND PPO met                 | 495   | 2000  | 3000
OOP IND PPO Remaining           | 625   | 3000  | 3000
Deductible IND PAR              | 3000  | 3500  | 3000
...
```

**Metric Naming Convention:**
```
{Type} {Plan} {Network} [{Status}]

Type: "Deductible" or "OOP"
Plan: "IND" (Individual) or "FAM" (Family)
Network: "PPO", "PAR", or "OON"
Status: "" (limit), "met" (amount met), or "Remaining" (balance)

Examples:
- "Deductible IND PPO"           → Individual PPO deductible limit
- "Deductible IND PPO met"       → Amount met toward IND PPO deductible
- "Deductible IND PPO Remaining" → Remaining IND PPO deductible balance
- "OOP IND PPO"                  → Individual PPO OOP maximum
- "OOP IND PPO met"              → Amount met toward IND PPO OOP
- "OOP IND PPO Remaining"        → Remaining IND PPO OOP balance
```

---

## Data Structure

### Complete Response Structure

```python
{
    "found": True,
    "member_id": "M1001",

    # Individual plan deductibles/OOP
    "individual": {
        # In-network PPO
        "ppo": {
            "deductible": 2683,                 # Deductible limit
            "deductible_met": 1840,             # Amount met
            "deductible_remaining": 843,        # Remaining balance
            "oop": 1120,                        # OOP maximum
            "oop_met": 495,                     # Amount met
            "oop_remaining": 625                # Remaining balance
        },

        # Participating provider (PAR)
        "par": {
            "deductible": 3000,
            "deductible_met": 1500,
            "deductible_remaining": 1500,
            "oop": 5000,
            "oop_met": 2000,
            "oop_remaining": 3000
        },

        # Out-of-network (OON)
        "oon": {
            "deductible": 5000,
            "deductible_met": 0,
            "deductible_remaining": 5000,
            "oop": 10000,
            "oop_met": 0,
            "oop_remaining": 10000
        }
    },

    # Family plan deductibles/OOP
    "family": {
        "ppo": {
            "deductible": 5366,
            "deductible_met": 3680,
            "deductible_remaining": 1686,
            "oop": 2240,
            "oop_met": 990,
            "oop_remaining": 1250
        },
        "par": {...},
        "oon": {...}
    }
}
```

### Network Level Definitions

| Network | Description | Typical Cost |
|---------|-------------|--------------|
| **PPO** | Preferred Provider Organization - In-network | Lowest |
| **PAR** | Participating Provider - Still in-network but different tier | Medium |
| **OON** | Out-of-Network | Highest |

### Deductible vs OOP

| Term | Definition | Example |
|------|------------|---------|
| **Deductible** | Amount you must pay before insurance starts paying | $2,683 |
| **Deductible Met** | Amount you've already paid toward deductible | $1,840 |
| **Deductible Remaining** | Amount still needed to meet deductible | $843 |
| **OOP (Out-of-Pocket)** | Maximum total you'll pay in a year | $1,120 |
| **OOP Met** | Amount you've paid toward OOP maximum | $495 |
| **OOP Remaining** | Amount until you reach OOP maximum | $625 |

---

## Error Handling

### Error Types and Responses

#### 1. Missing member_id
```python
# No member_id provided
result = await agent.get_deductible_oop(member_id="")
# Raises: ValueError("member_id parameter is required")
```

#### 2. Member Not Found
```python
# Member has no deductible data
result = await agent.get_deductible_oop(member_id="M9999")
# Returns: {"found": False, "message": "No deductible/OOP data found for member M9999"}
```

#### 3. Database Error
```python
# Database connection failed
result = await agent.get_deductible_oop(member_id="M1001")
# Returns: {"error": "Lookup failed: Database error"}
```

#### 4. Configuration Error
```python
# Agent initialization failed
result = await agent.get_deductible_oop(member_id="M1001")
# Returns: {"error": "Lookup service unavailable: ..."}
```

---

## Testing

### Unit Tests

```python
import pytest
from src.MBA.agents.deductible_oop_agent import DeductibleOOPAgent

@pytest.mark.asyncio
async def test_get_deductible_oop_success():
    agent = DeductibleOOPAgent()
    result = await agent.get_deductible_oop(member_id="M1001")

    assert result["found"] == True
    assert result["member_id"] == "M1001"
    assert "individual" in result
    assert "family" in result
    assert "ppo" in result["individual"]
    assert "deductible" in result["individual"]["ppo"]

@pytest.mark.asyncio
async def test_get_deductible_oop_not_found():
    agent = DeductibleOOPAgent()
    result = await agent.get_deductible_oop(member_id="M9999")

    assert result["found"] == False
    assert "message" in result

@pytest.mark.asyncio
async def test_missing_member_id():
    agent = DeductibleOOPAgent()

    with pytest.raises(ValueError):
        await agent.get_deductible_oop(member_id="")
```

### Integration Tests

```bash
# Test via API
curl -X GET "http://localhost:8000/deductible_oop/M1001"

# Expected response:
# {
#   "found": true,
#   "member_id": "M1001",
#   "individual": {
#     "ppo": {
#       "deductible": 2683,
#       "deductible_met": 1840,
#       "deductible_remaining": 843,
#       ...
#     }
#   },
#   "family": {...}
# }
```

---

## Performance Considerations

### Transposed Table Performance
```
✅ Pros:
  - Single query fetches all metrics for one member
  - No JOINs required
  - Efficient for member-specific lookups

❌ Cons:
  - Adding new members requires ALTER TABLE
  - Not ideal for querying across members
  - Wide table structure
```

### Query Optimization
- Query retrieves all metrics in one shot (no multiple queries)
- `IS NOT NULL` filter reduces result set
- Data parsing in memory (fast)

---

## Security Features

### SQL Injection Prevention
⚠️ **Note**: This agent uses **dynamic column names** which cannot be fully parameterized:

```python
# Column name must be dynamic (member ID)
query = f"SELECT Metric, `{member_id}` as value FROM deductibles_oop"
```

**Mitigation:**
✅ Input validation (`.strip()`)
✅ Limited to alphanumeric member IDs
✅ Error handling prevents exposure

---

## Troubleshooting

### Issue: "No deductible/OOP data found"
**Cause**: Member has no data in deductibles_oop table
**Solution**: Verify member exists in memberdata, check ETL process

### Issue: "Lookup service unavailable"
**Cause**: Database connection failed
**Solution**: Check database credentials, network connectivity

### Issue: Incomplete data returned
**Cause**: Some metrics missing in database
**Solution**: Check ETL data completeness, verify metric naming

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
src.MBA.etl.db              # Database connection
```

---

## Related Documentation

- [Member Verification Agent README](../member_verification_agent/README.md)
- [Benefit Accumulator Agent README](../benefit_accumulator_agent/README.md)
- [Orchestration Agent README](../orchestration_agent/README.md)
- [Database ETL Documentation](../../etl/README.md)

---

## Changelog

### v1.0.0 (Initial Release)
- ✅ AWS Bedrock integration with Claude Sonnet 4.5
- ✅ Transposed table query support
- ✅ Hierarchical data parsing (plan type + network level)
- ✅ Batch lookup support
- ✅ Comprehensive error handling
- ✅ Direct tool call workaround for Strands limitation

---

## License

Copyright © 2025 MBA System. All rights reserved.
