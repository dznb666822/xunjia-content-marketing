"""Copy Evaluation Tool.

Uses heuristic scoring so tests run deterministically without LLM calls.
"""

from __future__ import annotations

import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class CopyEvaluationInput(BaseModel):
    copy_text: str = Field(..., description="Marketing copy to evaluate")
    channel: str = Field(default="general", description="Channel context")


class CopyEvaluationTool(BaseTool):
    name: str = "copy_evaluator"
    description: str = (
        "Evaluate marketing copy for clarity, persuasion and fit for channel."
    )
    args_schema: Type[BaseModel] = CopyEvaluationInput

    def _run(self, copy_text: str, channel: str = "general") -> str:
        text = copy_text.strip()
        word_count = len(text.split())
        char_count = len(text)
        sentence_count = max(1, text.count(".") + text.count("!") + text.count("?"))
        avg_sentence_length = word_count / sentence_count

        weak_words = ["maybe", "possibly", "somewhat", "very", "nice", "quite"]
        power_words = ["exclusive", "proven", "free", "limited", "save", "now"]

        weak_hits = sum(1 for w in weak_words if w in text.lower())
        power_hits = sum(1 for w in power_words if w in text.lower())

        clarity = max(0.0, 1.0 - (weak_hits * 0.1))
        emotional = min(1.0, power_hits * 0.2)
        cta_strength = 1.0 if any(k in text.lower() for k in ["buy", "sign up", "get", "pre-order", "try"]) else 0.5

        channel_limits = {
            "social_media": 280,
            "search_ads": 90,
            "email": 1200,
        }
        limit = channel_limits.get(channel, 1000)
        length_score = 1.0 if char_count <= limit else max(0.0, 1.0 - ((char_count - limit) / max(limit, 1)))

        readability = 1.0 if avg_sentence_length <= 20 else 0.7

        overall = round((clarity + emotional + cta_strength + length_score + readability) / 5, 2)

        suggestions = []
        if power_hits == 0:
            suggestions.append("Add power words (e.g., 'exclusive', 'proven', 'free').")
        if length_score < 0.7:
            suggestions.append(f"Copy is too long for {channel}. Trim to fit limits.")
        if cta_strength < 0.8:
            suggestions.append("Strengthen the CTA — use a clear action verb.")
        if not suggestions:
            suggestions.append("Copy looks solid — minor tweaks at most.")

        payload = {
            "overall_score": overall,
            "scores": {
                "readability": round(readability, 2),
                "emotional_impact": round(emotional, 2),
                "clarity": round(clarity, 2),
                "cta_strength": round(cta_strength, 2),
                "length_appropriateness": round(length_score, 2),
            },
            "metrics": {
                "word_count": word_count,
                "character_count": char_count,
                "sentence_count": sentence_count,
                "avg_sentence_length": round(avg_sentence_length, 1),
                "power_words_found": power_hits,
                "weak_words_found": weak_hits,
                "channel_char_limit": limit,
            },
            "suggestions": suggestions,
        }
        return json.dumps(payload, indent=2)
