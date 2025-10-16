"""
AWS Bedrock Access Test Script for MBA System

This script tests access to all required AWS Bedrock models:
1. Claude 3.5 Sonnet v2 (LLM)
2. Titan Embeddings v2 (Embeddings)
3. Cohere Rerank v3.5 (Reranking)

Usage:
    python test_bedrock_access.py

Requirements:
    - boto3 installed
    - AWS credentials configured (profile or environment variables)
    - AWS Bedrock model access enabled
    - IAM permissions for bedrock:InvokeModel
"""

import boto3
import json
import os
import sys
from typing import Tuple

# Configuration
REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
# Use cross-region inference profile for Claude (required for on-demand access)
CLAUDE_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
# Titan Embeddings v2 produces 1024 dimensions (not 1536)
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"
TITAN_EXPECTED_DIMENSION = 1024  # v2 uses 1024, not 1536
# Cohere Rerank v3.5
COHERE_MODEL_ID = "cohere.rerank-v3-5:0"


def get_bedrock_client():
    """Get Bedrock runtime client with proper credentials."""
    try:
        # Check if running in Lambda
        is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

        if is_lambda:
            print(f"Running in Lambda environment")
            session = boto3.Session(region_name=REGION)
        else:
            print(f"Running locally")
            session_kwargs = {'region_name': REGION}

            # Use profile if specified
            aws_profile = os.getenv('AWS_PROFILE')
            if aws_profile:
                print(f"Using AWS profile: {aws_profile}")
                session_kwargs['profile_name'] = aws_profile

            session = boto3.Session(**session_kwargs)

        client = session.client('bedrock-runtime', region_name=REGION)
        print(f"✅ Bedrock client created for region: {REGION}")
        return client

    except Exception as e:
        print(f"❌ Failed to create Bedrock client: {e}")
        sys.exit(1)


def test_claude(client) -> Tuple[bool, str]:
    """Test Claude 3.5 Sonnet v2 model access."""
    print("\n" + "=" * 60)
    print("TEST 1: Claude 3.5 Sonnet v2 (LLM)")
    print("=" * 60)

    try:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "user",
                    "content": "Say exactly: 'AWS Bedrock Claude is working correctly!'"
                }
            ]
        }

        print(f"Model ID: {CLAUDE_MODEL_ID}")
        print(f"Sending request to Claude...")

        response = client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        answer = result['content'][0]['text']

        print(f"✅ Response received:")
        print(f"   {answer}")
        print(f"   Stop reason: {result.get('stop_reason', 'N/A')}")
        print(f"   Input tokens: {result.get('usage', {}).get('input_tokens', 'N/A')}")
        print(f"   Output tokens: {result.get('usage', {}).get('output_tokens', 'N/A')}")

        return True, answer

    except client.exceptions.AccessDeniedException as e:
        error_msg = f"Access Denied: Check IAM permissions for bedrock:InvokeModel"
        print(f"❌ {error_msg}")
        print(f"   Error: {str(e)}")
        return False, error_msg

    except client.exceptions.ResourceNotFoundException as e:
        error_msg = f"Model not found: Verify model access is enabled in Bedrock console"
        print(f"❌ {error_msg}")
        print(f"   Error: {str(e)}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


def test_titan_embeddings(client) -> Tuple[bool, str]:
    """Test Titan Embeddings v2 model access."""
    print("\n" + "=" * 60)
    print("TEST 2: Titan Embeddings v2 (Embeddings)")
    print("=" * 60)

    try:
        test_text = "Massage therapy is a covered benefit under this policy."

        payload = {
            "inputText": test_text
        }

        print(f"Model ID: {TITAN_MODEL_ID}")
        print(f"Generating embedding for: '{test_text}'")

        response = client.invoke_model(
            modelId=TITAN_MODEL_ID,
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        embedding = result['embedding']
        token_count = result.get('inputTextTokenCount', 'N/A')

        print(f"✅ Embedding generated successfully:")
        print(f"   Dimension: {len(embedding)}")
        print(f"   Token count: {token_count}")
        print(f"   First 5 values: {embedding[:5]}")
        print(f"   Vector norm: {sum(x**2 for x in embedding)**0.5:.4f}")

        # Verify dimension
        if len(embedding) != TITAN_EXPECTED_DIMENSION:
            error_msg = f"Warning: Expected {TITAN_EXPECTED_DIMENSION} dimensions, got {len(embedding)}"
            print(f"⚠️  {error_msg}")
            return False, error_msg

        return True, f"Generated {len(embedding)}-dimensional embedding"

    except client.exceptions.AccessDeniedException as e:
        error_msg = f"Access Denied: Check IAM permissions for Titan Embeddings"
        print(f"❌ {error_msg}")
        print(f"   Error: {str(e)}")
        return False, error_msg

    except client.exceptions.ResourceNotFoundException as e:
        error_msg = f"Model not found: Verify Titan Embeddings v2 access is enabled"
        print(f"❌ {error_msg}")
        print(f"   Error: {str(e)}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


def test_cohere_rerank(client) -> Tuple[bool, str]:
    """Test Cohere Rerank v3.5 model access."""
    print("\n" + "=" * 60)
    print("TEST 3: Cohere Rerank v3.5 (Document Reranking)")
    print("=" * 60)

    try:
        query = "What is the coverage for massage therapy?"

        documents = [
            "Massage therapy is covered with a limit of 6 visits per calendar year. Prior authorization is not required.",
            "Physical therapy requires a referral from your primary care physician and prior authorization.",
            "Chiropractic care is limited to 20 visits per year with a $25 copay per visit.",
            "Acupuncture is not covered under this plan as it is considered an alternative therapy.",
            "Occupational therapy is covered when medically necessary with prior authorization from the insurance company."
        ]

        payload = {
            "api_version": 2,  # Cohere Rerank v3.5 requires api_version >= 2
            "query": query,
            "documents": documents,
            "top_n": min(5, len(documents))
        }

        print(f"Model ID: {COHERE_MODEL_ID}")
        print(f"Query: '{query}'")
        print(f"Documents to rerank: {len(documents)}")

        response = client.invoke_model(
            modelId=COHERE_MODEL_ID,
            body=json.dumps(payload)
        )

        result = json.loads(response['body'].read())
        reranked_results = result.get('results', [])

        print(f"✅ Reranking completed successfully:")
        print(f"   Reranked documents: {len(reranked_results)}")
        print(f"   Results (sorted by relevance):")

        for i, item in enumerate(reranked_results, 1):
            doc_index = item['index']
            relevance_score = item.get('relevance_score', 0.0)
            doc_preview = documents[doc_index][:80] + "..." if len(documents[doc_index]) > 80 else documents[doc_index]

            print(f"   {i}. Doc #{doc_index + 1} | Relevance: {relevance_score:.4f}")
            print(f"      '{doc_preview}'")

        # Verify top result is about massage therapy
        top_doc_index = reranked_results[0]['index']
        if "massage therapy" in documents[top_doc_index].lower():
            print(f"   ✅ Top result correctly identified massage therapy document")
        else:
            print(f"   ⚠️  Warning: Top result may not be most relevant")

        return True, f"Reranked {len(reranked_results)} documents"

    except client.exceptions.AccessDeniedException as e:
        error_msg = f"Access Denied: Check IAM permissions for Cohere Rerank"
        print(f"❌ {error_msg}")
        print(f"   Error: {str(e)}")
        return False, error_msg

    except client.exceptions.ResourceNotFoundException as e:
        error_msg = f"Model not found: Verify Cohere Rerank v3.5 access is enabled"
        print(f"❌ {error_msg}")
        print(f"   Error: {str(e)}")
        return False, error_msg

    except client.exceptions.ValidationException as e:
        error_msg = f"Validation error: Check payload format"
        print(f"❌ {error_msg}")
        print(f"   Error: {str(e)}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg


def print_summary(results: list):
    """Print test summary."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed, message in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            print(f"       Error: {message}")

    print("=" * 60)

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("🎉 SUCCESS: All Bedrock models configured correctly!")
        print("\nNext steps:")
        print("  1. Your IAM permissions are working")
        print("  2. All required models are accessible")
        print("  3. You can now run the MBA RAG pipeline")
        print("\nTo test the full RAG pipeline:")
        print("  1. Upload a PDF: POST /upload/")
        print("  2. Prepare pipeline: POST /benefit-coverage-rag/prepare")
        print("  3. Query documents: POST /benefit-coverage-rag/query")
    else:
        print("⚠️  FAILURE: Some models failed configuration check")
        print("\nTroubleshooting steps:")
        print("  1. Check AWS Bedrock console for model access")
        print("  2. Verify IAM role/user has bedrock:InvokeModel permission")
        print("  3. Ensure you're using the correct AWS region")
        print("  4. Review the error messages above for details")
        print("\nRefer to AWS_BEDROCK_CONFIGURATION.md for detailed setup instructions")

    print("=" * 60)

    return all_passed


def main():
    """Main test execution."""
    print("=" * 60)
    print("AWS BEDROCK ACCESS TEST FOR MBA SYSTEM")
    print("=" * 60)
    print(f"Region: {REGION}")
    print(f"Testing 3 Bedrock models:")
    print(f"  1. Claude 3.5 Sonnet v2 (LLM)")
    print(f"  2. Titan Embeddings v2 (Embeddings)")
    print(f"  3. Cohere Rerank v3.5 (Reranking)")
    print("=" * 60)

    # Get Bedrock client
    client = get_bedrock_client()

    # Run tests
    results = []

    # Test 1: Claude
    claude_passed, claude_msg = test_claude(client)
    results.append(("Claude 3.5 Sonnet v2", claude_passed, claude_msg))

    # Test 2: Titan Embeddings
    titan_passed, titan_msg = test_titan_embeddings(client)
    results.append(("Titan Embeddings v2", titan_passed, titan_msg))

    # Test 3: Cohere Rerank
    cohere_passed, cohere_msg = test_cohere_rerank(client)
    results.append(("Cohere Rerank v3.5", cohere_passed, cohere_msg))

    # Print summary
    all_passed = print_summary(results)

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
