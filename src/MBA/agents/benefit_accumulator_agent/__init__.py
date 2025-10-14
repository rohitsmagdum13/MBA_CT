"""
Benefit Accumulator Agent package.

This package provides AWS Bedrock-powered benefit accumulator lookup
using Strands agent orchestration and RDS MySQL backend integration.

Exports:
    BenefitAccumulatorAgent: High-level async lookup interface
    benefit_accumulator_agent: Underlying Strands agent instance
    get_benefit_accumulator: Core lookup tool function
    BENEFIT_ACCUMULATOR_SYSTEM_PROMPT: System prompt for the agent

Example:
    from MBA.agents.benefit_accumulator_agent import BenefitAccumulatorAgent

    agent = BenefitAccumulatorAgent()
    result = await agent.get_benefit_accumulator(member_id="M1001")

    if result.get("found"):
        print(f"Found {len(result['benefits'])} benefits")
"""

from .wrapper import BenefitAccumulatorAgent
from .agent import benefit_accumulator_agent
from .tools import get_benefit_accumulator
from .prompt import BENEFIT_ACCUMULATOR_SYSTEM_PROMPT

__all__ = [
    "BenefitAccumulatorAgent",
    "benefit_accumulator_agent",
    "get_benefit_accumulator",
    "BENEFIT_ACCUMULATOR_SYSTEM_PROMPT"
]
