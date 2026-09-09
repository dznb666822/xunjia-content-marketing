"""Central configuration module.

Loads environment variables and provides validated settings
used across all agents, tools, and workflows.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
	"""Immutable application settings loaded once from environment."""

	llm_provider: str = field(
		default_factory=lambda: os.getenv("LLM_PROVIDER", "groq").lower()
	)
	groq_api_key: str = field(
		default_factory=lambda: os.getenv("GROQ_API_KEY", "")
	)
	groq_model: str = field(
		default_factory=lambda: os.getenv(
			"GROQ_MODEL", "llama-3.3-70b-versatile"
		)
	)
	temperature: float = field(
		default_factory=lambda: float(
			os.getenv("GROQ_TEMPERATURE", os.getenv("TEMPERATURE", "0.7"))
		)
	)
	groq_max_tokens: int = field(
		default_factory=lambda: int(os.getenv("GROQ_MAX_TOKENS", "1400"))
	)
	groq_rate_limit_retries: int = field(
		default_factory=lambda: int(os.getenv("GROQ_RATE_LIMIT_RETRIES", "3"))
	)
	groq_retry_base_seconds: float = field(
		default_factory=lambda: float(os.getenv("GROQ_RETRY_BASE_SECONDS", "8"))
	)
	groq_retry_max_seconds: float = field(
		default_factory=lambda: float(os.getenv("GROQ_RETRY_MAX_SECONDS", "45"))
	)
	serper_api_key: str = field(
		default_factory=lambda: os.getenv("SERPER_API_KEY", "")
	)
	output_dir: Path = field(
		default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "src/output"))
	)
	debug_mode: bool = field(
		default_factory=lambda: os.getenv("DEBUG_MODE", "false").lower() in ("true", "1")
	)

	def __post_init__(self) -> None:
		if not self.groq_api_key:
			raise EnvironmentError(
				"GROQ_API_KEY is required. Set it in your .env file."
			)
		if self.groq_max_tokens <= 0:
			raise EnvironmentError("GROQ_MAX_TOKENS must be greater than 0.")
		if self.groq_rate_limit_retries < 0:
			raise EnvironmentError(
				"GROQ_RATE_LIMIT_RETRIES cannot be negative."
			)
		if self.groq_retry_base_seconds <= 0:
			raise EnvironmentError(
				"GROQ_RETRY_BASE_SECONDS must be greater than 0."
			)
		if self.groq_retry_max_seconds <= 0:
			raise EnvironmentError(
				"GROQ_RETRY_MAX_SECONDS must be greater than 0."
			)
		# Ensure output directory exists
		self.output_dir.mkdir(parents=True, exist_ok=True)

	@property
	def has_serper(self) -> bool:
		"""Check whether real web-search is available."""
		return bool(self.serper_api_key)


# Module-level singleton — import this everywhere
settings = Settings()
