from __future__ import annotations

from typing import List

from google.adk.agents.llm_agent import Agent

from app.config import settings


SYSTEM_PROMPT = """You are ANKOR Voice Agent.
Your job is to help a coach create an evaluation from speech.
Ask concise clarification questions when required data is missing or ambiguous.
Never finalize unless the user explicitly confirms.
Use the provided tools to look up templates, teams, athletes, and subskills.
Return short, direct responses suited for voice.
"""


def build_root_agent(tools: List[object]) -> Agent:
    """
    Returns the ADK root agent instance.
    """
    return Agent(
        name="ankor_voice_agent",
        model=settings.live_model,
        description="Voice agent for ANKOR evaluations.",
        instruction=SYSTEM_PROMPT,
        tools=tools,
    )
