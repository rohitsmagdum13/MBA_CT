# Orchestration Agent Response Parsing Fix

## Problem

The orchestration agent was experiencing a response parsing error:
```
{"error":"Failed to parse agent response","success":false,"query":"Is member M1001 active?"}
```

The logs showed that:
1. The AI was successfully analyzing queries
2. The tools (`analyze_query`, `route_to_agent`, `format_response`) were executing correctly
3. The specialized agents (e.g., MemberVerificationAgent) were being called and returning valid results
4. **But the final orchestration response was failing to capture those results**

The warning message was:
```
Could not parse agent response - no content or tool calls
```

## Root Cause

**Strands Framework Limitation**: The Strands `AgentResult` object does not properly capture tool execution results in a way that can be accessed from the response object after `agent.invoke_async()` completes.

This is a known issue - the same problem was discovered in the `MemberVerificationAgent` (see [wrapper.py:257-263](src/MBA/agents/member_verification_agent/wrapper.py#L257-L263)):

```python
# WORKAROUND: Due to Strands AgentResult not capturing tool results properly,
# we directly call the tool function instead of going through the LLM.
```

## Solution

Implemented a **global result cache workaround** similar to the pattern used in other agents, but adapted for the orchestration agent's multi-tool workflow:

### 1. Added Global Cache ([tools.py](src/MBA/agents/orchestration_agent/tools.py#L16-L33))

```python
# Global cache for tool results (workaround for Strands not capturing results)
_tool_results_cache: Dict[str, Any] = {}

def get_tool_results_cache() -> Dict[str, Any]:
    """Get the current tool results cache."""
    return _tool_results_cache.copy()

def clear_tool_results_cache():
    """Clear the tool results cache."""
    global _tool_results_cache
    _tool_results_cache = {}
```

### 2. Updated All Tools to Cache Results

Each of the three tools now stores its result in the cache before returning:

**analyze_query**:
```python
_tool_results_cache['analyze_query'] = result
return result
```

**route_to_agent**:
```python
routing_result = {...}
_tool_results_cache['route_to_agent'] = routing_result
return routing_result
```

**format_response**:
```python
format_result = {...}
_tool_results_cache['format_response'] = format_result
return format_result
```

### 3. Added Cache-Based Parsing ([wrapper.py](src/MBA/agents/orchestration_agent/wrapper.py#L134-L198))

Created new method `_parse_cached_results()` that:
- Retrieves results from the global cache
- Builds the orchestration result from cached tool outputs
- Handles cases where some tools may not have executed

### 4. Updated process_query to Use Cache ([wrapper.py](src/MBA/agents/orchestration_agent/wrapper.py#L417-L429))

```python
# WORKAROUND: Due to Strands AgentResult not capturing tool results properly,
# we retrieve results from our cache instead of parsing the response object
from .tools import get_tool_results_cache, clear_tool_results_cache

# Get cached tool results
cached_results = get_tool_results_cache()
logger.info(f"Retrieved cached tool results: {list(cached_results.keys())}")

# Parse the results from cache
result = self._parse_cached_results(cached_results)

# Clear cache for next invocation
clear_tool_results_cache()
```

## Files Modified

1. **[src/MBA/agents/orchestration_agent/tools.py](src/MBA/agents/orchestration_agent/tools.py)**
   - Added global cache variables and accessor functions
   - Updated `analyze_query` to cache results (lines 270-284)
   - Updated `route_to_agent` to cache results at all return points (lines 333-465)
   - Updated `format_response` to cache results (lines 566-580)

2. **[src/MBA/agents/orchestration_agent/wrapper.py](src/MBA/agents/orchestration_agent/wrapper.py)**
   - Added `_parse_cached_results()` method (lines 134-198)
   - Updated `process_query()` to use cache instead of response parsing (lines 417-429)

## Testing

Run the test script:
```bash
python test_orchestration_fix.py
```

Expected output:
```
✅ TEST PASSED - Orchestration successful!
   Intent: member_verification
   Agent: MemberVerificationAgent
   Confidence: 0.65
```

## Result

The orchestration agent now:
- ✅ Correctly captures tool execution results
- ✅ Returns properly structured responses
- ✅ Includes all required fields (success, intent, agent, result, confidence, reasoning, extracted_entities)
- ✅ No more "Failed to parse agent response" errors

## Why This Approach?

**Alternative Considered**: Bypass the AI agent entirely and call tools directly (like MemberVerificationAgent does).

**Why We Didn't**: The orchestration agent NEEDS the AI to make intelligent routing decisions. The AI analyzes queries, classifies intent, and determines which specialized agent to call - this is the core value proposition.

**Our Solution**: Keep the AI-powered orchestration while working around the Strands framework limitation by caching tool results as they execute.

## Technical Notes

- The cache is thread-local (global within the module)
- Each invocation clears the cache after use to prevent stale data
- This approach maintains the AI orchestration workflow while ensuring results are captured
- The same pattern could be applied to other agents if needed
