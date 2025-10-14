# Bedrock Model ID Configuration Flow

## Complete Configuration Path

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     BEDROCK MODEL ID FLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

1. Environment Variable (.env file)
   ├─ File: .env:6-7
   └─ Value: BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-20250219-v1:0
   ↓
2. Settings Class (Pydantic loads from .env)
   ├─ File: src/MBA/core/settings.py:76-77
   ├─ Class: Settings
   └─ Field: bedrock_model_id: str = "anthropic.claude-3-7-sonnet-20250219-v1:0"
   ↓
3. Agent Initialization (uses settings.bedrock_model_id)
   ├─ File: src/MBA/agents/agent.py:95-100
   ├─ Import: from ..core.settings import settings
   └─ Agent Creation:
       verification_agent = Agent(
           name="MemberVerificationAgent",
           system_prompt=SYSTEM_PROMPT,
           tools=[verify_member],
           model=settings.bedrock_model_id  # ← MODEL ID USED HERE
       )
   ↓
4. Strands Agent Framework
   ├─ Receives model ID string
   ├─ Automatically creates BedrockModel client
   ├─ Configures AWS SDK with credentials from environment
   └─ Ready to invoke Bedrock LLM
   ↓
5. Runtime Invocation (when verify_member is called)
   ├─ File: src/MBA/agents/wrapper.py:265
   ├─ Call: response = await self._agent.invoke_async(user_message)
   └─ Bedrock API Call:
       └─→ bedrock-runtime.us-east-1.amazonaws.com
           └─→ InvokeModel API
               └─→ Model: anthropic.claude-3-7-sonnet-20250219-v1:0
```

## File-by-File Breakdown

### 1. `.env` (Root Directory)
```bash
# Line 6-7
BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-20250219-v1:0
```
**Purpose**: Store the model ID as an environment variable

---

### 2. `src/MBA/core/settings.py`
```python
# Line 76-77
bedrock_model_id: str = "anthropic.claude-3-7-sonnet-20250219-v1:0"
```
**Purpose**:
- Pydantic automatically loads `BEDROCK_MODEL_ID` from `.env`
- Provides type validation and default value
- Makes model ID available throughout the application via `settings.bedrock_model_id`

**How it works**:
```python
# Line 117-122
model_config = SettingsConfigDict(
    env_file=".env",          # ← Loads from .env
    env_file_encoding="utf-8",
    case_sensitive=False,      # ← BEDROCK_MODEL_ID → bedrock_model_id
    extra="ignore",
)
```

---

### 3. `src/MBA/agents/agent.py`

#### Import Settings (Line 30)
```python
from ..core.settings import settings
```

#### Setup AWS Credentials (Line 37-71)
```python
def _setup_aws_credentials():
    """Set up AWS credentials in environment for Bedrock access."""
    os.environ['AWS_ACCESS_KEY_ID'] = settings.aws_access_key_id
    os.environ['AWS_SECRET_ACCESS_KEY'] = settings.aws_secret_access_key
    os.environ['AWS_DEFAULT_REGION'] = settings.aws_default_region
```
**Purpose**: Configure AWS credentials so Strands can authenticate with Bedrock

#### Create Agent with Model ID (Line 95-100)
```python
verification_agent = Agent(
    name="MemberVerificationAgent",
    system_prompt=SYSTEM_PROMPT,
    tools=[verify_member],
    model=settings.bedrock_model_id  # ← USING MODEL ID FROM SETTINGS
)
```
**Purpose**: Pass the model ID to Strands Agent, which will:
1. Recognize it's a Bedrock model ID
2. Create a `BedrockModel` client internally
3. Use AWS credentials from environment to authenticate

#### Logging (Line 102-109)
```python
logger.info(
    "Member Verification Agent initialized successfully",
    extra={
        "agent_name": verification_agent.name,
        "tools_count": 1,
        "model_type": "AWS Bedrock",
        "model_id": settings.bedrock_model_id  # ← LOGGED FOR VERIFICATION
    }
)
```
**Purpose**: Log the model ID so you can verify which model is being used

---

### 4. `src/MBA/agents/wrapper.py`

#### LLM Invocation (Line 265)
```python
response = await self._agent.invoke_async(user_message)
```
**Purpose**: This is where the actual Bedrock API call happens:
1. Strands Agent receives the user message
2. Uses the configured `BedrockModel` client
3. Calls AWS Bedrock InvokeModel API with model ID
4. Returns the response

---

## How to Verify It's Working

### 1. Check the Logs on Startup
When you start the API or Streamlit app, you should see:

```
2025-10-14 13:06:09 | INFO | MBA.agents.agent:_setup_aws_credentials:63 |
    Using explicit AWS credentials from settings

2025-10-14 13:06:09 | INFO | MBA.agents.agent:<module>:77 |
    Bedrock configuration ready
    {'model_id': 'anthropic.claude-3-7-sonnet-20250219-v1:0', 'region': 'us-east-1'}

2025-10-14 13:06:09 | INFO | MBA.agents.agent:<module>:103 |
    Member Verification Agent initialized successfully
    {'agent_name': 'MemberVerificationAgent', 'tools_count': 1,
     'model_type': 'AWS Bedrock',
     'model_id': 'anthropic.claude-3-7-sonnet-20250219-v1:0'}
```

### 2. Check During Verification
When you verify a member, you should see:

```
============================================================
EXECUTING VERIFICATION WITH BEDROCK LLM
============================================================
📤 Sending to Bedrock: Verify the member with member ID M1001...
🤖 Calling AWS Bedrock LLM via Strands Agent...
📥 Bedrock LLM response received
✅ Verification completed via Bedrock
```

### 3. Test the Configuration
```bash
# Verify settings are loaded correctly
uv run python -c "from MBA.core.settings import settings; print(f'Model ID: {settings.bedrock_model_id}')"
# Expected output: Model ID: anthropic.claude-3-7-sonnet-20250219-v1:0
```

---

## How to Change the Model

### Option 1: Update .env file
```bash
# Edit .env
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0  # Different model
```
Then restart the application.

### Option 2: Set Environment Variable
```bash
# Windows CMD
set BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
uv run python -m uvicorn MBA.microservices.api:app --reload

# Windows PowerShell
$env:BEDROCK_MODEL_ID="anthropic.claude-3-5-sonnet-20241022-v2:0"
uv run python -m uvicorn MBA.microservices.api:app --reload

# Linux/Mac
export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
uv run python -m uvicorn MBA.microservices.api:app --reload
```

---

## Available Bedrock Claude Models

- `anthropic.claude-3-7-sonnet-20250219-v1:0` ← **Current/Latest**
- `anthropic.claude-3-5-sonnet-20241022-v2:0`
- `anthropic.claude-3-5-sonnet-20240620-v1:0`
- `anthropic.claude-3-opus-20240229-v1:0`
- `anthropic.claude-3-haiku-20240307-v1:0`

---

## Benefits of This Architecture

1. **Centralized Configuration**: Model ID defined once in `.env`
2. **Type Safety**: Pydantic validates the model ID
3. **Easy Updates**: Change model by editing `.env` file
4. **Environment-Specific**: Different model IDs for dev/staging/prod
5. **Logged**: Model ID logged on startup for verification
6. **No Code Changes**: Change models without touching code

---

**Last Updated**: 2025-10-14
**Current Model**: Claude 3.7 Sonnet (`anthropic.claude-3-7-sonnet-20250219-v1:0`)
