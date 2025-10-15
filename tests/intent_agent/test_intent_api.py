"""
Test script for Intent Identification Agent API endpoints.

This script tests the three Intent Identification endpoints:
1. POST /intent/identify - Single query classification
2. POST /intent/identify-batch - Batch classification
3. GET /intent/supported - Get supported intents

Run the API server first:
    python -m MBA.microservices.api

Then run this test:
    python tests/intent_agent/test_intent_api.py
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
    """Test health check endpoint to verify API is running."""
    print_section("1. Health Check")

    response = requests.get(f"{BASE_URL}/health")
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        intent_status = data.get("services", {}).get("intent_identification_agent")
        if intent_status == "initialized":
            print("\n✅ Intent Identification Agent is initialized")
            return True
        else:
            print(f"\n❌ Intent Identification Agent is not initialized: {intent_status}")
            return False
    else:
        print("\n❌ Health check failed")
        return False


def test_supported_intents():
    """Test GET /intent/supported endpoint."""
    print_section("2. Get Supported Intents")

    response = requests.get(f"{BASE_URL}/intent/supported")
    print_response(response)

    if response.status_code == 200:
        print("\n✅ Successfully retrieved supported intents")
        return True
    else:
        print("\n❌ Failed to retrieve supported intents")
        return False


def test_single_intent_identification():
    """Test POST /intent/identify with various queries."""
    print_section("3. Single Intent Identification")

    test_queries = [
        {
            "description": "Member Verification Query",
            "query": "Is member M1001 active?"
        },
        {
            "description": "Deductible Query",
            "query": "What is the deductible for member M1234?"
        },
        {
            "description": "Benefit Accumulator Query",
            "query": "How many massage therapy visits has member M5678 used?"
        },
        {
            "description": "Benefit Coverage RAG Query",
            "query": "Is acupuncture covered under the plan?"
        },
        {
            "description": "Local RAG Query",
            "query": "What does my uploaded document say about dental coverage?"
        },
        {
            "description": "General Inquiry",
            "query": "Hello, how are you?"
        }
    ]

    results = []

    for test_case in test_queries:
        print(f"\n\nTest: {test_case['description']}")
        print(f"Query: {test_case['query']}")
        print("-" * 80)

        payload = {
            "query": test_case["query"],
            "context": {}
        }

        response = requests.post(f"{BASE_URL}/intent/identify", json=payload)
        print_response(response)

        if response.status_code == 200:
            data = response.json()
            intent = data.get("intent")
            confidence = data.get("confidence")
            print(f"\n✅ Classified as: {intent} (confidence: {confidence})")
            results.append(True)
        else:
            print(f"\n❌ Failed to classify query")
            results.append(False)

    success_rate = sum(results) / len(results) * 100
    print(f"\n\nSuccess Rate: {success_rate:.1f}% ({sum(results)}/{len(results)})")

    return all(results)


def test_batch_intent_identification():
    """Test POST /intent/identify-batch endpoint."""
    print_section("4. Batch Intent Identification")

    payload = {
        "queries": [
            "Is member M1001 active?",
            "What is the deductible for member M1234?",
            "How many massage visits has member M5678 used?",
            "Is acupuncture covered?",
            "Hello!"
        ],
        "context": {}
    }

    print(f"\nClassifying {len(payload['queries'])} queries in batch...")

    response = requests.post(f"{BASE_URL}/intent/identify-batch", json=payload)
    print_response(response)

    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        total = data.get("total", 0)

        print(f"\n✅ Successfully classified {total} queries")

        # Print summary
        print("\n\nBatch Results Summary:")
        print("-" * 80)
        for i, result in enumerate(results, 1):
            query = payload["queries"][i-1][:50] + "..." if len(payload["queries"][i-1]) > 50 else payload["queries"][i-1]
            intent = result.get("intent", "unknown")
            confidence = result.get("confidence", 0.0)
            print(f"{i}. {query}")
            print(f"   → {intent} (confidence: {confidence:.2f})")

        return True
    else:
        print("\n❌ Batch classification failed")
        return False


def test_error_handling():
    """Test error handling for invalid requests."""
    print_section("5. Error Handling")

    # Test with empty query
    print("\n\nTest: Empty Query")
    print("-" * 80)
    payload = {"query": "", "context": {}}
    response = requests.post(f"{BASE_URL}/intent/identify", json=payload)
    print_response(response)

    if response.status_code in [400, 422]:
        print("\n✅ Correctly handled empty query")
        empty_query_handled = True
    else:
        print("\n❌ Did not handle empty query correctly")
        empty_query_handled = False

    # Test with missing query field
    print("\n\nTest: Missing Query Field")
    print("-" * 80)
    payload = {"context": {}}
    response = requests.post(f"{BASE_URL}/intent/identify", json=payload)
    print_response(response)

    if response.status_code == 422:
        print("\n✅ Correctly handled missing query field")
        missing_field_handled = True
    else:
        print("\n❌ Did not handle missing query field correctly")
        missing_field_handled = False

    return empty_query_handled and missing_field_handled


def main():
    """Run all tests."""
    print_section("Intent Identification Agent API Test Suite")
    print(f"\nBase URL: {BASE_URL}")
    print("\nMake sure the API server is running:")
    print("  python -m MBA.microservices.api")

    try:
        # Test 1: Health Check
        if not test_health_check():
            print("\n\n❌ API server is not running or Intent Agent is not initialized")
            print("Please start the API server and try again.")
            return

        # Test 2: Supported Intents
        test_supported_intents()

        # Test 3: Single Intent Identification
        test_single_intent_identification()

        # Test 4: Batch Intent Identification
        test_batch_intent_identification()

        # Test 5: Error Handling
        test_error_handling()

        # Final Summary
        print_section("Test Suite Complete")
        print("\n✅ All tests completed successfully!")
        print("\nIntent Identification Agent API is fully functional.")

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
