"""
Shared helpers for building CrewAI agents.

Centralises the LLM instance so every agent uses the same
model / temperature unless explicitly overridden.
"""

from __future__ import annotations

from crewai.llm import LLM

from src.config import settings


class BaseAgent:
    """Lightweight base class for non-CrewAI agent tests."""

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get("name", "Agent")
        self.role = kwargs.get("role", "")
        self.goal = kwargs.get("goal", "")
        self.backstory = kwargs.get("backstory", "")


def get_llm(
    model: str | None = None,
    temperature: float | None = None,
) -> LLM:
    """Return a configured LLM via CrewAI's LiteLLM backend.

    Supports any LiteLLM provider via LLM_PROVIDER (e.g. "groq", "deepseek").
    Model string format: "{provider}/{model_name}".
    """
    model_name = model or settings.groq_model
    return LLM(
        model=f"{settings.llm_provider}/{model_name}",
        temperature=temperature if temperature is not None else settings.temperature,
        api_key=settings.groq_api_key,
        max_tokens=settings.groq_max_tokens,
    )
