"""
Test script to verify orchestration agent fix.
"""
import asyncio
import json


async def test_orchestration():
    """Test orchestration with member verification query."""
    # Import after defining the async function to avoid import-time issues
    from src.MBA.agents.orchestration_agent.wrapper import OrchestrationAgent
    from src.MBA.core.logging_config import setup_root_logger

    setup_root_logger()

    agent = OrchestrationAgent()

    query = "Is member M1001 active?"
    print(f"\n{'='*70}")
    print(f"Testing Query: {query}")
    print(f"{'='*70}\n")

    try:
        result = await agent.process_query(query)

        print(f"\n{'='*70}")
        print("ORCHESTRATION RESULT:")
        print(f"{'='*70}")
        print(json.dumps(result, indent=2))
        print(f"{'='*70}\n")

        # Verify key fields
        assert "success" in result, "Result missing 'success' field"
        assert "intent" in result, "Result missing 'intent' field"
        assert "agent" in result, "Result missing 'agent' field"
        assert "result" in result, "Result missing 'result' field"

        if result.get("success"):
            print("✅ TEST PASSED - Orchestration successful!")
            print(f"   Intent: {result.get('intent')}")
            print(f"   Agent: {result.get('agent')}")
            print(f"   Confidence: {result.get('confidence')}")
            return 0
        else:
            print("❌ TEST FAILED - Orchestration returned success=False")
            if "error" in result:
                print(f"   Error: {result['error']}")
            return 1

    except Exception as e:
        print(f"❌ TEST FAILED - Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_orchestration())
    exit(exit_code)
