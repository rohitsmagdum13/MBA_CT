# AWS Bedrock Integration in Member Verification Agent

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MEMBER VERIFICATION FLOW                            │
└─────────────────────────────────────────────────────────────────────────────┘

1. User Request (Streamlit/API)
   ↓
2. MemberVerificationAgent.verify_member() [wrapper.py:173]
   ↓
3. Build Natural Language Prompt [wrapper.py:113-132]
   Example: "Verify the member with member ID M1001 and date of birth 2005-05-23"
   ↓
4. *** AWS BEDROCK LLM INVOCATION *** [wrapper.py:265]
   └─→ self._agent.invoke_async(user_message)
       ├─→ Strands Agent Framework
       ├─→ AWS Bedrock Runtime Client [agent.py:85]
       ├─→ Claude Sonnet 4.5 Model
       └─→ System Prompt [prompt.py:15-40]
   ↓
5. Bedrock LLM Analyzes Request
   ├─→ Understands natural language query
   ├─→ Identifies need to call verify_member tool
   └─→ Extracts parameters: {member_id, dob, name}
   ↓
6. Bedrock Calls verify_member Tool [tools.py:101]
   ↓
7. Tool Executes SQL Query against RDS MySQL [tools.py:169-171]
   ↓
8. Database Returns Results
   ↓
9. Tool Returns Structured JSON [tools.py:184-196]
   ↓
10. Bedrock Formats Final Response
   ↓
11. Parse Agent Response [wrapper.py:134-171]
   ↓
12. Return to User

```

## Code Locations Where Bedrock is Used

### 1. **Environment Configuration**
**File:** `.env:6-7`
```bash
# AWS Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-20250219-v1:0
```

### 2. **Settings Configuration**
**File:** `src/MBA/core/settings.py:76-77`
```python
# ---------------- AWS Bedrock Configuration ----------------
bedrock_model_id: str = "anthropic.claude-3-7-sonnet-20250219-v1:0"
```
This loads from the `.env` file and provides the model ID to the agent.

### 3. **AWS Credentials Setup**
**File:** `src/MBA/agents/agent.py:37-71`
```python
def _setup_aws_credentials():
    """Set up AWS credentials in environment for Bedrock access."""
    os.environ['AWS_ACCESS_KEY_ID'] = settings.aws_access_key_id
    os.environ['AWS_SECRET_ACCESS_KEY'] = settings.aws_secret_access_key
    os.environ['AWS_DEFAULT_REGION'] = settings.aws_default_region
```
Configures AWS credentials so Strands can authenticate with Bedrock.

### 4. **Strands Agent Creation with Bedrock Model ID**
**File:** `src/MBA/agents/agent.py:95-100`
```python
verification_agent = Agent(
    name="MemberVerificationAgent",
    system_prompt=SYSTEM_PROMPT,
    tools=[verify_member],
    model=settings.bedrock_model_id  # ← BEDROCK MODEL ID FROM SETTINGS
)
```
The Strands Agent automatically creates a BedrockModel client using this model ID string.

### 5. **Bedrock LLM Invocation**
**File:** `src/MBA/agents/wrapper.py:265`
```python
# This line actually calls AWS Bedrock!
response = await self._agent.invoke_async(user_message)
# ↑ Strands sends the message to Bedrock Claude 3.7 Sonnet
```

### 6. **System Prompt for Bedrock**
**File:** `src/MBA/agents/prompt.py:15-40`
```python
SYSTEM_PROMPT = """You are a Member Verification Agent...
Your sole responsibility is to authenticate member identities...
Call the verify_member tool with the exact parameters provided...
"""
```

## How to Verify Bedrock is Being Used

### Check the Logs
When you run a verification, you'll see these log messages:

```
2025-10-14 13:06:09 | INFO | MBA.agents.agent:_create_bedrock_client:87 |
    Bedrock client initialized: region=us-east-1

2025-10-14 13:10:15 | INFO | MBA.agents.wrapper:verify_member:253 |
    ============================================================
    EXECUTING VERIFICATION WITH BEDROCK LLM
    ============================================================

2025-10-14 13:10:15 | INFO | MBA.agents.wrapper:verify_member:259 |
    📤 Sending to Bedrock: Verify the member with member ID M1001...

2025-10-14 13:10:15 | INFO | MBA.agents.wrapper:verify_member:264 |
    🤖 Calling AWS Bedrock LLM via Strands Agent...

2025-10-14 13:10:17 | INFO | MBA.agents.wrapper:verify_member:266 |
    📥 Bedrock LLM response received

2025-10-14 13:10:17 | INFO | MBA.agents.wrapper:verify_member:274 |
    ✅ Verification completed via Bedrock
```

## AWS Credentials Configuration

Bedrock requires AWS credentials. Configuration is in `src/MBA/core/settings.py`:

```python
aws_access_key_id: Optional[str] = None
aws_secret_access_key: Optional[str] = None
aws_default_region: str = "us-east-1"
aws_profile: Optional[str] = None
```

Set via environment variables or `.env` file:
```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=us-east-1

# AWS Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-20250219-v1:0
```

## Bedrock Model Details

- **Service**: AWS Bedrock Runtime
- **Model**: Claude 3.7 Sonnet (`anthropic.claude-3-7-sonnet-20250219-v1:0`)
- **Region**: us-east-1 (default)
- **Endpoint**: bedrock-runtime.us-east-1.amazonaws.com
- **Configuration**: Model ID loaded from `.env` → `settings.py` → `agent.py`

## Why Use Bedrock?

1. **Natural Language Understanding**: Bedrock's LLM can understand queries like:
   - "Verify member M1001"
   - "Check if John Doe born on 1990-01-15 is a valid member"
   - "Authenticate member with ID M1002 and DOB 1987-12-14"

2. **Tool Orchestration**: Bedrock decides:
   - Which tool to call (verify_member)
   - What parameters to pass
   - How to format the response

3. **Intelligent Error Handling**: Bedrock can:
   - Handle ambiguous requests
   - Request missing information
   - Provide contextual error messages

## Difference from Direct SQL

**WITHOUT Bedrock (Direct SQL):**
```python
# Direct approach - rigid
result = db.query("SELECT * FROM memberdata WHERE member_id = ?", ["M1001"])
```

**WITH Bedrock (Current Implementation):**
```python
# Intelligent approach - flexible
user_input = "Verify member M1001 with birth date 2005-05-23"
result = await agent.verify_member(member_id="M1001", dob="2005-05-23")
# Bedrock understands the intent and calls the right tool
```

## Test Commands

### API Test (with Bedrock):
```bash
curl -X POST "http://127.0.0.1:8000/verify/member" \
  -H "Content-Type: application/json" \
  -d '{"member_id": "M1001", "dob": "2005-05-23"}'
```

### Streamlit Test (with Bedrock):
```bash
uv run streamlit run src/MBA/ui/streamlit_app.py
# Navigate to "👤 Member Verification" tab
```

### Check Bedrock Logs:
Watch your terminal logs for the "EXECUTING VERIFICATION WITH BEDROCK LLM" message!

---

**Last Updated**: 2025-10-14
**Integration Status**: ✅ **ACTIVE - Bedrock is now fully integrated**
