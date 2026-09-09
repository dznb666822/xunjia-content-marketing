"""Trend Research Tool.

If a Serper API key is configured the tool performs a real web search;
otherwise it falls back to an LLM-free simulated analysis so the
project works out of the box without extra API keys.
"""

from __future__ import annotations

import json
from typing import Any, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.config import settings


class TrendResearchInput(BaseModel):
    """Input schema — keeps the agent's calls predictable."""

    query: str = Field(..., description="The market/trend research query")
    industry: str = Field(
        default="general", description="Industry vertical to focus on"
    )


class TrendResearchTool(BaseTool):
    name: str = "trend_research"
    description: str = (
        "Research current market trends, consumer behaviour and industry "
        "developments for a given topic. Returns structured trend data."
    )
    args_schema: Type[BaseModel] = TrendResearchInput

    def _run(self, query: str, industry: str = "general") -> str:
        """Execute the tool — live search or simulated."""
        if settings.has_serper:
            return self._live_search(query, industry)
        return self._simulated_search(query, industry)

    # ── Private helpers ──────────────────────────────────────────────

    def _live_search(self, query: str, industry: str) -> str:
        """Perform a real Serper.dev Google search."""
        search_query = f"{query} {industry} trends 2025"
        headers = {
            "X-API-KEY": settings.serper_api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": search_query, "num": 10}

        try:
            resp = httpx.post(
                "https://google.serper.dev/search",
                headers=headers,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._format_serper_results(data, query, industry)
        except httpx.HTTPError as exc:
            return (
                f"Live search failed ({exc}); falling back to analysis.\n"
                + self._simulated_search(query, industry)
            )

    def _format_serper_results(
        self, data: dict[str, Any], query: str, industry: str
    ) -> str:
        lines = [
            f"## Trend Research Results: {query} ({industry})\n",
            "### Top Search Results\n",
        ]
        for item in data.get("organic", [])[:7]:
            lines.append(
                f"- **{item.get('title', 'N/A')}**\n"
                f"  {item.get('snippet', 'No snippet')}\n"
                f"  Source: {item.get('link', 'N/A')}\n"
            )
        if knowledge := data.get("knowledgeGraph"):
            lines.append("### Knowledge Panel\n")
            lines.append(
                f"- {knowledge.get('title', '')}: "
                f"{knowledge.get('description', 'N/A')}\n"
            )
        return "\n".join(lines)

    def _simulated_search(self, query: str, industry: str) -> str:
        """LLM-free heuristic fallback — enough for demos & tests."""
        analysis: dict[str, Any] = {
            "query": query,
            "industry": industry,
            "analysis_type": "simulated_trend_research",
            "trends": [
                {
                    "name": "AI-Powered Personalisation",
                    "description": (
                        "Brands are leveraging AI to create hyper-personalised "
                        "customer experiences across all touchpoints."
                    ),
                    "relevance": 0.95,
                },
                {
                    "name": "Sustainability-First Messaging",
                    "description": (
                        "Consumers increasingly favour brands with transparent "
                        "and genuine sustainability commitments."
                    ),
                    "relevance": 0.85,
                },
                {
                    "name": "Short-Form Video Dominance",
                    "description": (
                        "TikTok, Reels, and Shorts continue to deliver the "
                        "highest organic engagement rates."
                    ),
                    "relevance": 0.90,
                },
                {
                    "name": "Community-Led Growth",
                    "description": (
                        "Building owned communities (Discord, Slack, forums) "
                        "drives retention and advocacy."
                    ),
                    "relevance": 0.80,
                },
            ],
            "consumer_insights": [
                "78 % of consumers prefer brands that personalise experiences.",
                "Gen-Z audiences respond best to authentic, unpolished content.",
                "Trust in influencer marketing is plateauing — micro-influencers outperform.",
            ],
            "note": (
                "This is a simulated analysis. Set SERPER_API_KEY for live data."
            ),
        }
        return json.dumps(analysis, indent=2)
