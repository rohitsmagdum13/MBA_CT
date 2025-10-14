"""
Test script for Intent Identification Agent.

This script tests the intent classification agent with various sample queries
to verify it correctly identifies intents and extracts entities.

Run with: python test_intent_agent.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from MBA.agents import IntentIdentificationAgent


# Test queries for each intent
TEST_QUERIES = {
    "member_verification": [
        "Is member M1001 active?",
        "Check eligibility for member M5678",
        "Verify member status for ID M9999",
        "Is member M1234 enrolled?",
        "What is the status of member M4567?"
    ],
    "deductible_oop": [
        "What is the deductible for member M1001?",
        "How much has member M1234 paid toward their out-of-pocket maximum?",
        "Show OOP information for M5678",
        "What is the remaining deductible for member M9999?",
        "Has member M1111 met their deductible?"
    ],
    "benefit_accumulator": [
        "How many massage therapy visits has member M1001 used?",
        "What are the benefit limits for member M1234?",
        "Check chiropractic visit count for M5678",
        "Has member M9999 reached their limit for acupuncture?",
        "Show me the benefit accumulator for member M1001",
        "How many visits remaining for physical therapy for M2222?"
    ],
    "benefit_coverage_rag": [
        "Is massage therapy covered?",
        "What is the coverage for chiropractic care?",
        "What are the copays for emergency room visits?",
        "Tell me about preventive care benefits",
        "What services are covered at 100%?",
        "Is acupuncture covered and what are the limits?",
        "What is the deductible for this plan?",
        "Are mental health services covered?"
    ],
    "local_rag": [
        "What does the uploaded document say about massage therapy?",
        "Search the benefit PDF for acupuncture coverage",
        "What information is in the document about deductibles?",
        "Query the uploaded policy for mental health benefits"
    ],
    "general_inquiry": [
        "Hello",
        "Hi there",
        "What can you help me with?",
        "Tell me about the MBA system",
        "How do I use this?",
        "What services are available?"
    ]
}


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 80 + "\n")


def print_result(query: str, result: dict):
    """Print formatted classification result."""
    print(f"Query: \"{query}\"")
    print(f"Intent: {result.get('intent', 'N/A')}")
    print(f"Confidence: {result.get('confidence', 0.0):.2f}")
    print(f"Suggested Agent: {result.get('suggested_agent', 'N/A')}")

    entities = result.get('extracted_entities', {})
    if entities:
        print(f"Extracted Entities:")
        for key, value in entities.items():
            print(f"  - {key}: {value}")

    print(f"Reasoning: {result.get('reasoning', 'N/A')}")
    print(f"Fallback Intent: {result.get('fallback_intent', 'N/A')}")


async def test_single_query(agent: IntentIdentificationAgent, query: str):
    """Test a single query."""
    result = await agent.identify(query)
    return result


async def test_intent_category(agent: IntentIdentificationAgent, intent: str, queries: list):
    """Test all queries for a specific intent category."""
    print(f"\n{'─' * 80}")
    print(f"Testing Intent: {intent.upper().replace('_', ' ')}")
    print(f"{'─' * 80}\n")

    correct_count = 0
    total_count = len(queries)

    for idx, query in enumerate(queries, 1):
        result = await test_single_query(agent, query)

        # Check if classification is correct
        is_correct = result.get("intent") == intent
        status = "✓" if is_correct else "✗"

        print(f"{status} Test {idx}/{total_count}:")
        print_result(query, result)
        print()

        if is_correct:
            correct_count += 1

    accuracy = (correct_count / total_count) * 100 if total_count > 0 else 0
    print(f"Accuracy for {intent}: {correct_count}/{total_count} ({accuracy:.1f}%)")

    return correct_count, total_count


async def test_batch_classification(agent: IntentIdentificationAgent):
    """Test batch classification."""
    print_separator()
    print("TESTING BATCH CLASSIFICATION")
    print_separator()

    # Select sample queries from each intent
    batch_queries = [
        "Is member M1001 active?",
        "What is the deductible for member M1234?",
        "How many massage visits has member M5678 used?",
        "Is acupuncture covered?",
        "Search the document for chiropractic",
        "Hello, what can you do?"
    ]

    print(f"Processing {len(batch_queries)} queries in batch...\n")

    results = await agent.classify_batch(batch_queries)

    for idx, (query, result) in enumerate(zip(batch_queries, results), 1):
        print(f"Query {idx}:")
        print_result(query, result)
        print()

    print(f"Batch processing completed: {len(results)} results")


async def test_edge_cases(agent: IntentIdentificationAgent):
    """Test edge cases and error handling."""
    print_separator()
    print("TESTING EDGE CASES")
    print_separator()

    edge_cases = [
        ("Empty query", ""),
        ("Very long query", "Is massage therapy covered? " * 50),
        ("Multiple member IDs", "Compare benefits for member M1001 and M1234"),
        ("Ambiguous query", "Check the deductible"),
        ("Mixed intent", "Is member M1001 active and what are their massage therapy limits?"),
        ("Only member ID", "M1001"),
        ("No clear intent", "Lorem ipsum dolor sit amet")
    ]

    for test_name, query in edge_cases:
        print(f"Test: {test_name}")
        try:
            if query:  # Skip empty query test as it will raise ValueError
                result = await agent.identify(query)
                print_result(query, result)
            else:
                try:
                    result = await agent.identify(query)
                    print("ERROR: Should have raised ValueError for empty query")
                except ValueError as e:
                    print(f"Correctly raised ValueError: {e}")
        except Exception as e:
            print(f"Error: {e}")
        print()


async def main():
    """Main test function."""
    print_separator()
    print("INTENT IDENTIFICATION AGENT - COMPREHENSIVE TESTING")
    print_separator()

    print("Initializing Intent Identification Agent...")
    agent = IntentIdentificationAgent()

    print("Agent initialized successfully!")
    print(f"Supported Intents: {agent.get_supported_intents()}")
    print(f"Agent Mapping: {agent.get_agent_mapping()}")

    # Test each intent category
    total_correct = 0
    total_queries = 0

    for intent, queries in TEST_QUERIES.items():
        correct, total = await test_intent_category(agent, intent, queries)
        total_correct += correct
        total_queries += total

    # Test batch classification
    await test_batch_classification(agent)

    # Test edge cases
    await test_edge_cases(agent)

    # Overall summary
    print_separator()
    print("OVERALL TEST SUMMARY")
    print_separator()

    overall_accuracy = (total_correct / total_queries) * 100 if total_queries > 0 else 0

    print(f"Total Queries Tested: {total_queries}")
    print(f"Correctly Classified: {total_correct}")
    print(f"Overall Accuracy: {overall_accuracy:.1f}%")
    print()

    if overall_accuracy >= 90:
        print("✓ EXCELLENT: Agent performing very well!")
    elif overall_accuracy >= 75:
        print("✓ GOOD: Agent performing well with minor errors")
    elif overall_accuracy >= 60:
        print("⚠ FAIR: Agent needs improvement")
    else:
        print("✗ POOR: Agent requires significant tuning")

    print_separator()


if __name__ == "__main__":
    asyncio.run(main())
