"""
Deductible/OOP Agent package.

This package provides AWS Bedrock-powered deductible and out-of-pocket
lookup using Strands agent orchestration and RDS MySQL backend integration.

Exports:
    DeductibleOOPAgent: High-level async lookup interface
    deductible_oop_agent: Underlying Strands agent instance
    get_deductible_oop: Core lookup tool function
    DEDUCTIBLE_OOP_SYSTEM_PROMPT: System prompt for the agent

Example:
    from MBA.agents.deductible_oop_agent import DeductibleOOPAgent

    agent = DeductibleOOPAgent()
    result = await agent.get_deductible_oop(member_id="M1001")

    if result.get("found"):
        print(f"Deductible PPO: {result['individual']['ppo']['deductible']}")
"""

from .wrapper import DeductibleOOPAgent
from .agent import deductible_oop_agent
from .tools import get_deductible_oop
from .prompt import DEDUCTIBLE_OOP_SYSTEM_PROMPT

__all__ = [
    "DeductibleOOPAgent",
    "deductible_oop_agent",
    "get_deductible_oop",
    "DEDUCTIBLE_OOP_SYSTEM_PROMPT"
]
