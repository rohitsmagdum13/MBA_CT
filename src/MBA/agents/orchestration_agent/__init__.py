"""
Orchestration Agent for intelligent multi-agent routing.

This module provides the central orchestration layer for the MBA system,
analyzing user queries and routing them to appropriate specialized agents
based on intent classification.

The Orchestration Agent:
- Identifies user intent using IntentIdentificationAgent
- Routes queries to specialized agents (Member Verification, Deductible/OOP, etc.)
- Manages multi-agent workflows for complex queries
- Provides unified response format across all agents
- Maintains conversation context (optional)

Architecture:
    User Query → Orchestration Agent → Intent Identification → Route to Agent → Response

Supported Agents:
    - MemberVerificationAgent: Member eligibility and status
    - DeductibleOOPAgent: Deductible and out-of-pocket queries
    - BenefitAccumulatorAgent: Benefit usage and accumulation
    - BenefitCoverageRAGAgent: Policy coverage questions
    - LocalRAGAgent: User-uploaded document queries

Exports:
    OrchestrationAgent: High-level async orchestration interface

Example:
    from MBA.agents import OrchestrationAgent

    # Initialize orchestration agent
    agent = OrchestrationAgent()

    # Process a single query (automatic routing)
    result = await agent.process_query("Is member M1001 active?")

    if result.get("success"):
        print(f"Intent: {result['intent']}")
        print(f"Agent: {result['agent']}")
        print(f"Result: {result['result']}")

    # Process batch queries
    queries = [
        "Is member M1001 active?",
        "What is the deductible for member M1234?",
        "How many massage visits has member M5678 used?"
    ]
    results = await agent.process_batch(queries)

    # Check conversation history
    history = agent.get_conversation_history()
"""

from .wrapper import OrchestrationAgent

__all__ = [
    "OrchestrationAgent"
]

__version__ = "1.0.0"
