"""
Debug script to inspect Strands agent response structure.
"""
import asyncio
import sys
from src.MBA.agents.orchestration_agent.wrapper import OrchestrationAgent
from src.MBA.core.logging_config import setup_root_logger, get_logger

setup_root_logger()
logger = get_logger(__name__)


async def debug_response():
    """Test orchestration and inspect response structure."""
    agent = OrchestrationAgent()

    query = "Is member M1001 active?"
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing query: {query}")
    logger.info(f"{'='*70}\n")

    try:
        result = await agent.process_query(query)

        logger.info(f"\n{'='*70}")
        logger.info("FINAL RESULT:")
        logger.info(f"{'='*70}")
        logger.info(f"Result: {result}")
        logger.info(f"{'='*70}\n")

        return result

    except Exception as e:
        logger.error(f"Error during testing: {str(e)}", exc_info=True)
        return None


if __name__ == "__main__":
    result = asyncio.run(debug_response())

    if result:
        print("\n" + "="*70)
        print("SUCCESS - Result returned:")
        print("="*70)
        print(f"Success: {result.get('success')}")
        print(f"Intent: {result.get('intent')}")
        print(f"Agent: {result.get('agent')}")
        print(f"Confidence: {result.get('confidence')}")
        if 'error' in result:
            print(f"Error: {result.get('error')}")
        print("="*70)
    else:
        print("\nFAILED - No result returned")
        sys.exit(1)
