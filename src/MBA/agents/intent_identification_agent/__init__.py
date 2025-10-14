"""
Intent Identification Agent for MBA System.

This agent analyzes user queries and identifies the appropriate agent/service
to handle the request. It acts as an intelligent router for the MBA system.

Supported Intents:
- member_verification: Verify member eligibility and status
- deductible_oop: Query deductible and out-of-pocket information
- benefit_accumulator: Check benefit accumulation and limits
- benefit_coverage_rag: Query benefit coverage policies
- local_rag: Query uploaded benefit documents
- general_inquiry: General questions not specific to above categories

The agent uses AWS Bedrock with Claude Sonnet 4.5 for intent classification
and confidence scoring.
"""

from .wrapper import IntentIdentificationAgent

__all__ = ["IntentIdentificationAgent"]
