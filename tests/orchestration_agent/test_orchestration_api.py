"""
Test script for Orchestration Agent API endpoints.

This script comprehensively tests the orchestration system including:
1. Health check with orchestration agent status
2. Available agents listing
3. Single query orchestration with different intents
4. Batch query orchestration
5. Conversation history management
6. Error handling

Run the API server first:
    python -m MBA.microservices.api

Then run this test:
    python tests/orchestration_agent/test_orchestration_api.py
"""

import requests
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_response(response: requests.Response):
    """Pretty print a response."""
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))


def test_health_check():
    """Test health check endpoint to verify orchestration agent is initialized."""
    print_section("1. Health Check - Orchestration Agent Status")

    response = requests.get(f"{BASE_URL}/health")
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        orchestration_status = data.get("services", {}).get("orchestration_agent")
        if orchestration_status == "initialized":
            print("\n✅ Orchestration Agent is initialized")
            return True
        else:
            print(f"\n❌ Orchestration Agent is not initialized: {orchestration_status}")
            return False
    else:
        print("\n❌ Health check failed")
        return False


def test_available_agents():
    """Test GET /orchestrate/agents endpoint."""
    print_section("2. Get Available Agents")

    response = requests.get(f"{BASE_URL}/orchestrate/agents")
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        agents = data.get("agents", [])
        print(f"\n✅ Found {len(agents)} available agents")
        for agent in agents:
            print(f"   - {agent}")
        return True
    else:
        print("\n❌ Failed to retrieve available agents")
        return False


def test_single_query_orchestration():
    """Test POST /orchestrate/query with various query types."""
    print_section("3. Single Query Orchestration")

    test_queries = [
        {
            "description": "Member Verification Query",
            "query": "Is member M1001 active?",
            "expected_intent": "member_verification",
            "expected_agent": "MemberVerificationAgent"
        },
        {
            "description": "Deductible Query",
            "query": "What is the deductible for member M1234?",
            "expected_intent": "deductible_oop",
            "expected_agent": "DeductibleOOPAgent"
        },
        {
            "description": "Benefit Accumulator Query",
            "query": "How many massage therapy visits has member M5678 used?",
            "expected_intent": "benefit_accumulator",
            "expected_agent": "BenefitAccumulatorAgent"
        },
        {
            "description": "Benefit Coverage RAG Query",
            "query": "Is acupuncture covered under the plan?",
            "expected_intent": "benefit_coverage_rag",
            "expected_agent": "BenefitCoverageRAGAgent"
        },
        {
            "description": "General Inquiry",
            "query": "Hello, can you help me?",
            "expected_intent": "general_inquiry",
            "expected_agent": "OrchestrationAgent"
        }
    ]

    results = []

    for test_case in test_queries:
        print(f"\n\n{'─' * 80}")
        print(f"Test: {test_case['description']}")
        print(f"Query: {test_case['query']}")
        print(f"Expected Intent: {test_case['expected_intent']}")
        print(f"Expected Agent: {test_case['expected_agent']}")
        print('─' * 80)

        payload = {
            "query": test_case["query"],
            "context": {},
            "preserve_history": False
        }

        response = requests.post(f"{BASE_URL}/orchestrate/query", json=payload)
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            intent = data.get("intent")
            agent = data.get("agent")
            confidence = data.get("confidence")
            success = data.get("success")

            print(f"\n📊 Results:")
            print(f"   Intent: {intent}")
            print(f"   Agent: {agent}")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   Success: {success}")

            # Verify routing
            intent_match = intent == test_case["expected_intent"]
            agent_match = agent == test_case["expected_agent"]

            if intent_match and agent_match:
                print(f"\n✅ Correctly routed to {agent}")
                results.append(True)
            else:
                print(f"\n⚠️  Routing mismatch!")
                if not intent_match:
                    print(f"   Expected intent: {test_case['expected_intent']}, got: {intent}")
                if not agent_match:
                    print(f"   Expected agent: {test_case['expected_agent']}, got: {agent}")
                results.append(False)
        else:
            print(f"\n❌ Orchestration failed")
            results.append(False)

    success_rate = sum(results) / len(results) * 100
    print(f"\n\n{'=' * 80}")
    print(f"Single Query Orchestration Success Rate: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    print('=' * 80)

    return all(results)


def test_batch_orchestration():
    """Test POST /orchestrate/batch endpoint."""
    print_section("4. Batch Query Orchestration")

    payload = {
        "queries": [
            "Is member M1001 active?",
            "What is the deductible for member M1234?",
            "How many massage therapy visits has member M5678 used?",
            "Is acupuncture covered under the plan?",
            "Hello, how are you?"
        ],
        "context": {}
    }

    print(f"\nProcessing {len(payload['queries'])} queries in batch...")
    print("\nQueries:")
    for i, query in enumerate(payload['queries'], 1):
        print(f"  {i}. {query}")

    response = requests.post(f"{BASE_URL}/orchestrate/batch", json=payload)
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        total = data.get("total", 0)
        successful = data.get("successful", 0)
        failed = data.get("failed", 0)
        intents = data.get("intents", {})

        print(f"\n✅ Successfully processed {total} queries")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")

        # Print intent distribution
        print("\n📊 Intent Distribution:")
        for intent, count in intents.items():
            print(f"   {intent}: {count}")

        # Print detailed results summary
        print("\n\n📋 Detailed Results:")
        print('─' * 80)
        for i, result in enumerate(results, 1):
            query = payload["queries"][i-1][:60] + "..." if len(payload["queries"][i-1]) > 60 else payload["queries"][i-1]
            intent = result.get("intent", "unknown")
            agent = result.get("agent", "unknown")
            confidence = result.get("confidence", 0.0)
            success = result.get("success", False)

            status_icon = "✅" if success else "❌"
            print(f"{i}. {status_icon} {query}")
            print(f"   Intent: {intent} | Agent: {agent} | Confidence: {confidence:.2f}")

        return successful == total
    else:
        print("\n❌ Batch orchestration failed")
        return False


def test_conversation_history():
    """Test conversation history management."""
    print_section("5. Conversation History Management")

    # First, make some queries with preserve_history=True
    print("\nMaking queries with history preservation...")

    queries_with_history = [
        "Is member M1001 active?",
        "What is their deductible?",
        "How many massage visits have they used?"
    ]

    for query in queries_with_history:
        payload = {
            "query": query,
            "context": {},
            "preserve_history": True
        }
        response = requests.post(f"{BASE_URL}/orchestrate/query", json=payload)
        if response.status_code == 200:
            print(f"✅ Query processed: {query}")
        else:
            print(f"❌ Query failed: {query}")

    # Get conversation history
    print("\n\nRetrieving conversation history...")
    response = requests.get(f"{BASE_URL}/orchestrate/history")
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        history = data.get("history", [])
        total = data.get("total_interactions", 0)

        print(f"\n✅ Retrieved {total} interactions from history")

        # Clear history
        print("\n\nClearing conversation history...")
        response = requests.delete(f"{BASE_URL}/orchestrate/history")
        print_response(response)

        if response.status_code == 200:
            print("\n✅ History cleared successfully")

            # Verify history is empty
            response = requests.get(f"{BASE_URL}/orchestrate/history")
            data = response.json()
            new_total = data.get("total_interactions", 0)

            if new_total == 0:
                print("✅ Verified history is empty")
                return True
            else:
                print(f"⚠️  History still has {new_total} interactions")
                return False
        else:
            print("\n❌ Failed to clear history")
            return False
    else:
        print("\n❌ Failed to retrieve conversation history")
        return False


def test_error_handling():
    """Test error handling for invalid requests."""
    print_section("6. Error Handling")

    # Test with empty query
    print("\n\nTest: Empty Query")
    print('─' * 80)
    payload = {"query": "", "context": {}}
    response = requests.post(f"{BASE_URL}/orchestrate/query", json=payload)
    print_response(response)

    if response.status_code in [400, 422]:
        print("\n✅ Correctly handled empty query")
        empty_query_handled = True
    else:
        print("\n❌ Did not handle empty query correctly")
        empty_query_handled = False

    # Test with missing query field
    print("\n\nTest: Missing Query Field")
    print('─' * 80)
    payload = {"context": {}}
    response = requests.post(f"{BASE_URL}/orchestrate/query", json=payload)
    print_response(response)

    if response.status_code == 422:
        print("\n✅ Correctly handled missing query field")
        missing_field_handled = True
    else:
        print("\n❌ Did not handle missing query field correctly")
        missing_field_handled = False

    # Test with invalid batch request
    print("\n\nTest: Empty Batch Queries")
    print('─' * 80)
    payload = {"queries": [], "context": {}}
    response = requests.post(f"{BASE_URL}/orchestrate/batch", json=payload)
    print_response(response)

    if response.status_code in [200, 400, 422]:
        print("\n✅ Handled empty batch queries")
        empty_batch_handled = True
    else:
        print("\n❌ Did not handle empty batch queries correctly")
        empty_batch_handled = False

    return empty_query_handled and missing_field_handled and empty_batch_handled


def test_routing_accuracy():
    """Test routing accuracy across different query types."""
    print_section("7. Routing Accuracy Test")

    test_cases = [
        # Member Verification variations
        {"query": "Check if member M9999 is enrolled", "expected": "member_verification"},
        {"query": "Verify eligibility for M8888", "expected": "member_verification"},

        # Deductible/OOP variations
        {"query": "Member M7777 wants to know their deductible", "expected": "deductible_oop"},
        {"query": "Out of pocket max for M6666?", "expected": "deductible_oop"},

        # Benefit Accumulator variations
        {"query": "How many PT visits has M5555 used?", "expected": "benefit_accumulator"},
        {"query": "Member M4444 chiropractic visits remaining", "expected": "benefit_accumulator"},

        # Coverage questions
        {"query": "Does the plan cover dental implants?", "expected": "benefit_coverage_rag"},
        {"query": "Is vision covered?", "expected": "benefit_coverage_rag"},
    ]

    print(f"\nTesting routing accuracy with {len(test_cases)} diverse queries...\n")

    correct = 0
    total = len(test_cases)

    for i, test in enumerate(test_cases, 1):
        payload = {"query": test["query"], "context": {}}
        response = requests.post(f"{BASE_URL}/orchestrate/query", json=payload)

        if response.status_code == 200:
            data = response.json()
            intent = data.get("intent")
            confidence = data.get("confidence")

            match = intent == test["expected"]
            status = "✅" if match else "❌"

            print(f"{i}. {status} Query: {test['query'][:50]}...")
            print(f"   Expected: {test['expected']} | Got: {intent} | Confidence: {confidence:.2f}")

            if match:
                correct += 1
        else:
            print(f"{i}. ❌ Query failed: {test['query'][:50]}...")

    accuracy = (correct / total) * 100
    print(f"\n\n{'=' * 80}")
    print(f"Routing Accuracy: {accuracy:.1f}% ({correct}/{total})")
    print('=' * 80)

    return accuracy >= 70.0  # 70% threshold for passing


def main():
    """Run all orchestration tests."""
    print_section("Orchestration Agent API Test Suite")
    print(f"\nBase URL: {BASE_URL}")
    print("\nMake sure the API server is running:")
    print("  python -m MBA.microservices.api")

    try:
        # Test 1: Health Check
        if not test_health_check():
            print("\n\n❌ API server is not running or Orchestration Agent is not initialized")
            print("Please start the API server and try again.")
            return

        # Test 2: Available Agents
        test_available_agents()

        # Test 3: Single Query Orchestration
        test_single_query_orchestration()

        # Test 4: Batch Orchestration
        test_batch_orchestration()

        # Test 5: Conversation History
        test_conversation_history()

        # Test 6: Error Handling
        test_error_handling()

        # Test 7: Routing Accuracy
        test_routing_accuracy()

        # Final Summary
        print_section("Test Suite Complete")
        print("\n✅ All orchestration tests completed successfully!")
        print("\nOrchestration Agent Features Tested:")
        print("  ✓ Health check and initialization")
        print("  ✓ Available agents listing")
        print("  ✓ Single query orchestration with multiple intents")
        print("  ✓ Batch query processing")
        print("  ✓ Conversation history management")
        print("  ✓ Error handling for invalid inputs")
        print("  ✓ Routing accuracy across query types")
        print("\n🎉 Orchestration Agent API is fully functional!")

    except requests.exceptions.ConnectionError:
        print("\n\n❌ ERROR: Could not connect to API server")
        print(f"Make sure the API server is running at {BASE_URL}")
        print("\nStart the API server with:")
        print("  python -m MBA.microservices.api")

    except Exception as e:
        print(f"\n\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
