"""
Comprehensive test suite for Orchestration Agent.

Tests all different query types across all supported intents:
1. Member Verification
2. Deductible/OOP
3. Benefit Accumulator
4. Benefit Coverage RAG
5. Local RAG
6. General Inquiry
"""
import asyncio
import json
from typing import List, Dict, Any


# Test queries organized by intent
TEST_QUERIES = {
    "member_verification": [
        # Basic member verification
        "Is member M1001 active?",
        "Check if member M1002 is eligible",
        "Verify member M1003",
        "Is M1004 a valid member?",

        # With date of birth
        "Verify member M1001 with DOB 2005-05-23",
        "Check member with date of birth 1990-01-01",

        # With name
        "Is Brandi Kim an active member?",
        "Verify member John Smith",

        # Status inquiries
        "What is the status of member M1001?",
        "Is member M1002 enrolled?",
        "Check enrollment for M1003",
    ],

    "deductible_oop": [
        # Basic deductible queries
        "What is the deductible for member M1001?",
        "Show deductible information for M1002",
        "Get deductible for M1003",

        # OOP queries
        "What is the out-of-pocket max for member M1001?",
        "Show OOP information for M1002",
        "What's the out of pocket maximum for M1003?",

        # Combined deductible/OOP
        "Show me deductible and OOP for member M1001",
        "What are the cost-sharing amounts for M1002?",
        "Get financial information for member M1003",

        # With amounts
        "How much has member M1001 paid towards their deductible?",
        "What's remaining on M1002's out-of-pocket max?",
    ],

    "benefit_accumulator": [
        # Service usage queries
        "How many massage visits has member M1001 used?",
        "Show massage therapy usage for M1002",
        "How many chiropractic visits has M1003 used?",

        # Remaining benefits
        "How many massage visits does M1001 have remaining?",
        "What's left for acupuncture for member M1002?",
        "Show remaining physical therapy visits for M1003",

        # Service limits
        "What is the limit for massage therapy for M1001?",
        "How many PT visits are allowed for M1002?",

        # Multiple service types
        "Show all benefit usage for member M1001",
        "What services has M1002 used?",
        "Get benefit accumulator for M1003",

        # Specific services
        "Massage visits for M1001",
        "Chiropractic usage for M1002",
        "Acupuncture count for M1003",
        "Physical therapy visits for M1004",
    ],

    "benefit_coverage_rag": [
        # Coverage questions
        "What is covered under massage therapy?",
        "Is acupuncture covered?",
        "What services are included in the benefit plan?",

        # Policy questions
        "What are the coverage limits for chiropractic care?",
        "Tell me about the massage therapy benefit",
        "What's the policy on physical therapy?",

        # Requirements
        "Do I need prior authorization for massage?",
        "Are there any restrictions on chiropractic care?",
        "What are the requirements for acupuncture coverage?",

        # General coverage
        "What benefits are covered?",
        "Explain the benefit coverage",
        "What does the plan cover?",
    ],

    "local_rag": [
        # Document queries (if documents are uploaded)
        "What does the uploaded document say about benefits?",
        "Search uploaded files for coverage information",
        "Query my documents about massage therapy",

        # Specific document questions
        "Find information in uploaded PDFs",
        "What's in my benefit documents?",
    ],

    "general_inquiry": [
        # Greetings
        "Hello",
        "Hi there",
        "Hey",

        # Help requests
        "What can you do?",
        "Help me",
        "What are your capabilities?",

        # General questions
        "How does this work?",
        "What is this system?",
        "Tell me about MBA",
    ],

    "edge_cases": [
        # Missing information
        "What is the deductible?",  # No member ID
        "How many visits?",  # No member ID or service
        "Check eligibility",  # No member ID

        # Invalid member IDs
        "Is member XYZ123 active?",
        "Check member ABC",

        # Ambiguous queries
        "Tell me about member M1001",  # Could be verification or deductible
        "M1001 information",

        # Multiple intents
        "Is member M1001 active and what's their deductible?",
        "Check M1002 eligibility and show massage usage",

        # Typos and variations
        "membr M1001",
        "dedcutible for M1002",
        "masage visits M1003",
    ],

    "complex_queries": [
        # Long queries
        "I need to verify if member M1001 is currently active and enrolled in the system, and also check their eligibility status",

        # Multiple data points
        "For member M1001 with date of birth 2005-05-23, verify their status and show me their benefit information",

        # Natural language variations
        "Can you tell me whether or not the member with ID M1001 has active coverage?",
        "I'd like to know about member M1002's deductible and out-of-pocket expenses",
        "Could you please check how many massage therapy sessions member M1003 has used so far this year?",
    ]
}


async def test_single_query(agent, query: str, query_type: str) -> Dict[str, Any]:
    """Test a single query."""
    try:
        result = await agent.process_query(query)

        return {
            "query": query,
            "type": query_type,
            "success": result.get("success", False),
            "intent": result.get("intent", "unknown"),
            "agent": result.get("agent", "Unknown"),
            "confidence": result.get("confidence", 0.0),
            "has_result": "result" in result,
            "error": result.get("error"),
            "full_result": result
        }
    except Exception as e:
        return {
            "query": query,
            "type": query_type,
            "success": False,
            "intent": "error",
            "agent": "None",
            "confidence": 0.0,
            "has_result": False,
            "error": str(e),
            "full_result": {}
        }


async def run_all_tests():
    """Run all test queries."""
    from src.MBA.agents.orchestration_agent.wrapper import OrchestrationAgent
    from src.MBA.core.logging_config import setup_root_logger

    setup_root_logger()

    print("="*80)
    print("ORCHESTRATION AGENT - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print()

    agent = OrchestrationAgent()

    all_results = []
    total_queries = sum(len(queries) for queries in TEST_QUERIES.values())
    current = 0

    for intent_type, queries in TEST_QUERIES.items():
        print(f"\n{'='*80}")
        print(f"Testing: {intent_type.upper()} ({len(queries)} queries)")
        print(f"{'='*80}\n")

        for query in queries:
            current += 1
            print(f"[{current}/{total_queries}] Testing: {query[:60]}...")

            result = await test_single_query(agent, query, intent_type)
            all_results.append(result)

            # Show quick summary
            status = "✅" if result["success"] else "❌"
            print(f"    {status} Intent: {result['intent']}, Agent: {result['agent']}, Confidence: {result['confidence']:.2f}")

            if result["error"]:
                print(f"    ⚠️  Error: {result['error'][:100]}")

            print()

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    successful = [r for r in all_results if r["success"]]
    failed = [r for r in all_results if not r["success"]]

    print(f"\nTotal Queries: {len(all_results)}")
    print(f"Successful: {len(successful)} ({len(successful)/len(all_results)*100:.1f}%)")
    print(f"Failed: {len(failed)} ({len(failed)/len(all_results)*100:.1f}%)")

    # Intent distribution
    print("\n" + "-"*80)
    print("INTENT CLASSIFICATION BREAKDOWN")
    print("-"*80)

    intent_counts = {}
    for result in all_results:
        intent = result["intent"]
        if intent not in intent_counts:
            intent_counts[intent] = {"total": 0, "successful": 0}
        intent_counts[intent]["total"] += 1
        if result["success"]:
            intent_counts[intent]["successful"] += 1

    for intent, counts in sorted(intent_counts.items()):
        success_rate = counts["successful"] / counts["total"] * 100
        print(f"{intent:30s}: {counts['total']:3d} queries ({counts['successful']:3d} successful, {success_rate:5.1f}%)")

    # Show failures
    if failed:
        print("\n" + "-"*80)
        print("FAILED QUERIES")
        print("-"*80)

        for result in failed:
            print(f"\n❌ Query: {result['query']}")
            print(f"   Expected Type: {result['type']}")
            print(f"   Detected Intent: {result['intent']}")
            print(f"   Error: {result['error']}")

    # Agent routing breakdown
    print("\n" + "-"*80)
    print("AGENT ROUTING BREAKDOWN")
    print("-"*80)

    agent_counts = {}
    for result in all_results:
        agent = result["agent"]
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    for agent, count in sorted(agent_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{agent:30s}: {count:3d} queries ({count/len(all_results)*100:5.1f}%)")

    # Average confidence by intent
    print("\n" + "-"*80)
    print("AVERAGE CONFIDENCE BY INTENT")
    print("-"*80)

    intent_confidence = {}
    for result in all_results:
        intent = result["intent"]
        if intent not in intent_confidence:
            intent_confidence[intent] = []
        intent_confidence[intent].append(result["confidence"])

    for intent, confidences in sorted(intent_confidence.items()):
        avg_conf = sum(confidences) / len(confidences)
        print(f"{intent:30s}: {avg_conf:.3f}")

    # Save detailed results to JSON
    output_file = "orchestration_test_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "summary": {
                "total_queries": len(all_results),
                "successful": len(successful),
                "failed": len(failed),
                "success_rate": len(successful) / len(all_results) * 100
            },
            "results": all_results
        }, f, indent=2)

    print(f"\n✅ Detailed results saved to: {output_file}")

    return all_results


async def test_specific_queries():
    """Quick test with specific queries."""
    from src.MBA.agents.orchestration_agent.wrapper import OrchestrationAgent
    from src.MBA.core.logging_config import setup_root_logger

    setup_root_logger()

    agent = OrchestrationAgent()

    # Pick one query from each category for quick testing
    quick_tests = [
        ("Is member M1001 active?", "member_verification"),
        ("What is the deductible for member M1001?", "deductible_oop"),
        ("How many massage visits has member M1001 used?", "benefit_accumulator"),
        ("What is covered under massage therapy?", "benefit_coverage_rag"),
        ("What can you do?", "general_inquiry"),
    ]

    print("="*80)
    print("QUICK TEST - One Query Per Intent Type")
    print("="*80)
    print()

    for query, expected_intent in quick_tests:
        print(f"Query: {query}")
        print(f"Expected Intent: {expected_intent}")

        result = await agent.process_query(query)

        print(f"Result:")
        print(f"  Success: {result.get('success')}")
        print(f"  Intent: {result.get('intent')}")
        print(f"  Agent: {result.get('agent')}")
        print(f"  Confidence: {result.get('confidence', 0):.3f}")

        if result.get("error"):
            print(f"  Error: {result['error']}")

        match = result.get('intent') == expected_intent
        print(f"  Intent Match: {'✅' if match else '❌'}")
        print()

    print("="*80)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        # Quick test mode
        asyncio.run(test_specific_queries())
    else:
        # Full test suite
        asyncio.run(run_all_tests())
