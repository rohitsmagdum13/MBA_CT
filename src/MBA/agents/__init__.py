"""
MBA Agents package for member services.

This package provides AWS Bedrock-powered agents for member verification,
deductible/OOP lookups, and benefit accumulator queries using Strands
agent orchestration and RDS MySQL backend integration.

Exports:
    MemberVerificationAgent: High-level async member verification interface
    DeductibleOOPAgent: High-level async deductible/OOP lookup interface
    BenefitAccumulatorAgent: High-level async benefit accumulator lookup interface
    verification_agent: Underlying Strands verification agent instance
    deductible_oop_agent: Underlying Strands deductible/OOP agent instance
    benefit_accumulator_agent: Underlying Strands benefit accumulator agent instance
    verify_member: Core verification tool function
    get_deductible_oop: Core deductible/OOP lookup tool function
    get_benefit_accumulator: Core benefit accumulator lookup tool function

Example:
    # Member Verification
    from MBA.agents import MemberVerificationAgent

    agent = MemberVerificationAgent()
    result = await agent.verify_member(member_id="M12345", dob="1990-01-01")

    if result.get("valid"):
        print(f"Verified: {result['name']}")

    # Deductible/OOP Lookup
    from MBA.agents import DeductibleOOPAgent

    agent = DeductibleOOPAgent()
    result = await agent.get_deductible_oop(member_id="M1001")

    if result.get("found"):
        print(f"Deductible PPO: {result['individual']['ppo']['deductible']}")

    # Benefit Accumulator Lookup
    from MBA.agents import BenefitAccumulatorAgent

    agent = BenefitAccumulatorAgent()
    result = await agent.get_benefit_accumulator(member_id="M1001")

    if result.get("found"):
        print(f"Found {len(result['benefits'])} benefits")
"""

from .member_verification_agent import (
    MemberVerificationAgent,
    verification_agent,
    verify_member
)
from .deductible_oop_agent import (
    DeductibleOOPAgent,
    deductible_oop_agent,
    get_deductible_oop
)
from .benefit_accumulator_agent import (
    BenefitAccumulatorAgent,
    benefit_accumulator_agent,
    get_benefit_accumulator
)

__all__ = [
    "MemberVerificationAgent",
    "DeductibleOOPAgent",
    "BenefitAccumulatorAgent",
    "verification_agent",
    "deductible_oop_agent",
    "benefit_accumulator_agent",
    "verify_member",
    "get_deductible_oop",
    "get_benefit_accumulator"
]

__version__ = "2.0.0"