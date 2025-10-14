#!/usr/bin/env python3
"""
Test script for Member Verification API.
Run this script while the API server is running to test the verification endpoints.

Usage:
    1. Start the API server: uv run python -m uvicorn MBA.microservices.api:app --reload
    2. Run this test: uv run python test_verification.py
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"


def test_health():
    """Test the health endpoint."""
    print("\n=== Testing Health Endpoint ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_single_verification():
    """Test single member verification with real data."""
    print("\n=== Testing Single Member Verification ===")

    # Test with real member from MemberData.csv
    payload = {
        "member_id": "M1001",
        "dob": "2005-05-23",
        "name": "Brandi Kim"
    }

    print(f"Request Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(
        f"{BASE_URL}/verify/member",
        json=payload
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    result = response.json()
    if result.get("valid"):
        print("✓ Member verified successfully!")
    else:
        print("✗ Member verification failed")

    return response.status_code == 200


def test_batch_verification():
    """Test batch member verification with real data."""
    print("\n=== Testing Batch Member Verification ===")

    # Test with real members from MemberData.csv
    payload = {
        "members": [
            {
                "member_id": "M1002",
                "dob": "1987-12-14",
                "name": "Anthony Brown"
            },
            {
                "member_id": "M1003",
                "dob": "2001-08-30",
                "name": "Kimberly Ramirez"
            },
            {
                "member_id": "M1004",
                "dob": "1977-12-10"
            }
        ]
    }

    print(f"Request Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(
        f"{BASE_URL}/verify/batch",
        json=payload
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    result = response.json()
    if "results" in result:
        verified = sum(1 for r in result["results"] if r.get("valid"))
        print(f"\n✓ Verified {verified}/{result['total']} members")

    return response.status_code == 200


if __name__ == "__main__":
    print("=" * 60)
    print("Member Verification API Test Suite")
    print("=" * 60)
    print(f"API Base URL: {BASE_URL}")
    print("\nMake sure the API server is running:")
    print("  uv run python -m uvicorn MBA.microservices.api:app --reload")
    print("=" * 60)

    try:
        # Test health endpoint first
        if test_health():
            print("\n✓ Health check passed")
        else:
            print("\n✗ Health check failed")
            exit(1)

        # Test single verification
        if test_single_verification():
            print("\n✓ Single verification test passed")
        else:
            print("\n✗ Single verification test failed")

        # Test batch verification
        if test_batch_verification():
            print("\n✓ Batch verification test passed")
        else:
            print("\n✗ Batch verification test failed")

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Cannot connect to API server")
        print("Make sure the server is running on http://127.0.0.1:8000")
        print("Run: uv run python -m uvicorn MBA.microservices.api:app --reload")
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")