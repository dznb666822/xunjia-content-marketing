"""Competitor Analysis Tool.

Provides deterministic competitor analysis output for tests and
usable structured output for the workflow.
"""

from __future__ import annotations

import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class CompetitorAnalysisInput(BaseModel):
    query: str = Field(..., description="Market or product category")
    num_competitors: int = Field(
        default=3, description="Number of competitors to include"
    )


class CompetitorAnalysisTool(BaseTool):
    name: str = "competitor_analysis"
    description: str = (
        "Analyse competitors, positioning, strengths, weaknesses and "
        "market gaps for a given category. Returns structured JSON."
    )
    args_schema: Type[BaseModel] = CompetitorAnalysisInput

    def _run(self, query: str, num_competitors: int = 3) -> str:
        competitors = []
        for idx in range(num_competitors):
            label = chr(ord("A") + idx)
            competitors.append(
                {
                    "name": f"Competitor {label}",
                    "market_position": (
                        "Market leader with established brand"
                        if idx == 0
                        else "Fast-growing challenger with innovative features"
                        if idx == 1
                        else "Niche player with loyal community"
                    ),
                    "strengths": [
                        "Strong brand recognition",
                        "Extensive distribution network",
                        "Competitive pricing",
                    ],
                    "weaknesses": [
                        "Slow to innovate",
                        "Poor customer support ratings",
                        "Limited personalisation options",
                    ],
                    "key_message": (
                        "Trusted by millions worldwide"
                        if idx == 0
                        else "The future of smart"
                        if idx == 1
                        else "Built for people who care"
                    ),
                    "estimated_market_share": f"{30 - idx * 8}%",
                }
            )

        payload = {
            "analysis_for": query,
            "methodology": (
                "Competitive positioning analysis using Porter's Five Forces "
                "lens combined with messaging audit."
            ),
            "competitors": competitors,
            "market_gaps": [
                "No competitor strongly owns the sustainability narrative.",
                "Customer onboarding experiences are universally mediocre.",
                "Underserved segments in the 25-34 age bracket.",
            ],
            "differentiation_opportunities": [
                "Lead with transparency and social proof.",
                "Invest in community-driven content.",
                "Offer a freemium tier to capture top-of-funnel.",
            ],
        }
        return json.dumps(payload, indent=2)
