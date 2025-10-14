"""
Member Verification Agent package.

This package provides AWS Bedrock-powered member identity verification
using Strands agent orchestration and RDS MySQL backend integration.

Exports:
    MemberVerificationAgent: High-level async verification interface
    verification_agent: Underlying Strands agent instance
    verify_member: Core verification tool function
    SYSTEM_PROMPT: System prompt for the agent

Example:
    from MBA.agents.member_verification_agent import MemberVerificationAgent

    agent = MemberVerificationAgent()
    result = await agent.verify_member(member_id="M12345", dob="1990-01-01")

    if result.get("valid"):
        print(f"Verified: {result['name']}")
"""

from .wrapper import MemberVerificationAgent
from .agent import verification_agent
from .tools import verify_member
from .prompt import SYSTEM_PROMPT

__all__ = [
    "MemberVerificationAgent",
    "verification_agent",
    "verify_member",
    "SYSTEM_PROMPT"
]
