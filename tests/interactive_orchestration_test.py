"""
Interactive Orchestration Agent Test Console.

Run this script to test queries interactively in the console.
"""
import asyncio
import json
import sys


def print_result(result: dict):
    """Pretty print orchestration result."""
    print("\n" + "="*80)
    print("ORCHESTRATION RESULT")
    print("="*80)

    # Status
    success = result.get("success", False)
    status = "✅ SUCCESS" if success else "❌ FAILED"
    print(f"\nStatus: {status}")

    # Core fields
    print(f"\nIntent: {result.get('intent', 'unknown')}")
    print(f"Agent: {result.get('agent', 'Unknown')}")
    print(f"Confidence: {result.get('confidence', 0.0):.3f}")

    # Reasoning
    if result.get("reasoning"):
        print(f"\nReasoning: {result['reasoning']}")

    # Extracted entities
    if result.get("extracted_entities"):
        print(f"\nExtracted Entities:")
        for key, value in result["extracted_entities"].items():
            print(f"  - {key}: {value}")

    # Result data
    if result.get("result"):
        print(f"\nResult Data:")
        result_data = result["result"]
        if isinstance(result_data, dict):
            for key, value in result_data.items():
                if key != "message" or len(str(value)) < 200:
                    print(f"  - {key}: {value}")
                else:
                    print(f"  - {key}: {str(value)[:200]}...")
        else:
            print(f"  {result_data}")

    # Error
    if result.get("error"):
        print(f"\n⚠️  Error: {result['error']}")

    # Formatted response (if available)
    if result.get("formatted_response"):
        print(f"\nFormatted Response:")
        print(f"{json.dumps(result['formatted_response'], indent=2)}")

    print("="*80)


async def interactive_mode():
    """Run interactive test console."""
    from src.MBA.agents.orchestration_agent.wrapper import OrchestrationAgent
    from src.MBA.core.logging_config import setup_root_logger

    # Setup logging with less verbosity for interactive mode
    setup_root_logger()

    print("="*80)
    print("ORCHESTRATION AGENT - INTERACTIVE TEST CONSOLE")
    print("="*80)
    print("\nInitializing agent...")

    agent = OrchestrationAgent()

    print("✅ Agent ready!")
    print("\nEnter queries to test (or 'quit' to exit)")
    print("Available commands:")
    print("  - Type any query to test orchestration")
    print("  - 'examples' - Show example queries")
    print("  - 'history' - Show conversation history")
    print("  - 'clear' - Clear conversation history")
    print("  - 'json' - Toggle JSON output mode")
    print("  - 'quit' or 'exit' - Exit console")
    print("="*80)

    json_mode = False
    query_count = 0

    while True:
        try:
            # Get user input
            print(f"\n[Query #{query_count + 1}]")
            query = input(">>> ").strip()

            if not query:
                continue

            # Handle commands
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break

            elif query.lower() == 'examples':
                print("\n📋 Example Queries:")
                print("\nMember Verification:")
                print("  • Is member M1001 active?")
                print("  • Verify member M1002")
                print("\nDeductible/OOP:")
                print("  • What is the deductible for member M1001?")
                print("  • Show OOP information for M1002")
                print("\nBenefit Accumulator:")
                print("  • How many massage visits has member M1001 used?")
                print("  • Show chiropractic usage for M1002")
                print("\nCoverage Questions:")
                print("  • What is covered under massage therapy?")
                print("  • Is acupuncture covered?")
                print("\nGeneral:")
                print("  • What can you do?")
                print("  • Help me")
                continue

            elif query.lower() == 'history':
                history = agent.get_conversation_history()
                if history:
                    print(f"\n📜 Conversation History ({len(history)} entries):")
                    for i, entry in enumerate(history, 1):
                        print(f"\n{i}. Query: {entry.get('query', 'N/A')[:60]}...")
                        print(f"   Intent: {entry.get('intent')}, Agent: {entry.get('agent')}")
                        print(f"   Success: {entry.get('success')}, Confidence: {entry.get('confidence', 0):.3f}")
                else:
                    print("\n📜 No conversation history (use preserve_history=True to track)")
                continue

            elif query.lower() == 'clear':
                agent.clear_conversation_history()
                print("\n🗑️  Conversation history cleared")
                continue

            elif query.lower() == 'json':
                json_mode = not json_mode
                status = "enabled" if json_mode else "disabled"
                print(f"\n🔧 JSON output mode {status}")
                continue

            # Process query
            print(f"\n⏳ Processing: {query[:60]}...")

            result = await agent.process_query(query, preserve_history=False)

            query_count += 1

            # Display result
            if json_mode:
                print("\nJSON Response:")
                print(json.dumps(result, indent=2))
            else:
                print_result(result)

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            print("\nContinuing...")


async def batch_mode(queries: list):
    """Run queries in batch mode."""
    from src.MBA.agents.orchestration_agent.wrapper import OrchestrationAgent
    from src.MBA.core.logging_config import setup_root_logger

    setup_root_logger()

    print("="*80)
    print(f"BATCH MODE - Processing {len(queries)} queries")
    print("="*80)

    agent = OrchestrationAgent()

    results = []
    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] {query}")

        result = await agent.process_query(query)

        success = "✅" if result.get("success") else "❌"
        print(f"{success} Intent: {result.get('intent')}, Agent: {result.get('agent')}")

        results.append({
            "query": query,
            "result": result
        })

    # Save results
    output_file = "batch_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Results saved to: {output_file}")

    return results


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Batch mode - read queries from arguments or file
        if sys.argv[1] == "--file" and len(sys.argv) > 2:
            # Read from file
            with open(sys.argv[2], 'r') as f:
                queries = [line.strip() for line in f if line.strip()]
            asyncio.run(batch_mode(queries))
        else:
            # Use arguments as queries
            queries = sys.argv[1:]
            asyncio.run(batch_mode(queries))
    else:
        # Interactive mode
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
