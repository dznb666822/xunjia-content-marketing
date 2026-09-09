"""Unit tests for custom tools — no LLM calls, no network."""

from __future__ import annotations

import json

import pytest

from src.tools import (
    CompetitorAnalysisTool,
    CopyEvaluationTool,
    ImagePromptGeneratorTool,
    TrendResearchTool,
)


class TestTrendResearchTool:
    def setup_method(self):
        self.tool = TrendResearchTool()

    def test_returns_valid_json(self):
        # Use simulated search to test deterministic JSON output
        result = self.tool._simulated_search(
            query="smart home devices", industry="technology"
        )
        data = json.loads(result)
        assert "trends" in data
        assert len(data["trends"]) >= 3

    def test_contains_consumer_insights(self):
        # Use simulated search to test deterministic JSON output
        result = self.tool._simulated_search("fitness apps", industry="wellness")
        data = json.loads(result)
        assert "consumer_insights" in data
        assert len(data["consumer_insights"]) >= 1


class TestCompetitorAnalysisTool:
    def setup_method(self):
        self.tool = CompetitorAnalysisTool()

    def test_returns_requested_competitor_count(self):
        data = json.loads(self.tool._run("air purifiers", num_competitors=4))
        assert len(data["competitors"]) == 4

    def test_includes_market_gaps(self):
        data = json.loads(self.tool._run("CRM software", num_competitors=2))
        assert "market_gaps" in data
        assert len(data["market_gaps"]) >= 1


class TestCopyEvaluationTool:
    def setup_method(self):
        self.tool = CopyEvaluationTool()

    def test_scores_strong_copy_high(self):
        strong = (
            "Discover exclusive savings. Transform your home today. "
            "Sign up now — free for 30 days!"
        )
        data = json.loads(self.tool._run(strong, channel="social_media"))
        assert data["overall_score"] >= 0.5

    def test_scores_weak_copy_lower(self):
        weak = (
            "This is a very nice product that does quite good stuff "
            "and maybe you should possibly consider it somewhat."
        )
        data = json.loads(self.tool._run(weak, channel="social_media"))
        assert data["scores"]["clarity"] < 0.8  # weak words penalised

    def test_length_penalty_for_search_ads(self):
        long_copy = "Buy now! " * 50  # Way over 90 chars
        data = json.loads(self.tool._run(long_copy, channel="search_ads"))
        assert data["scores"]["length_appropriateness"] < 0.5

    def test_returns_suggestions(self):
        data = json.loads(self.tool._run("Hello world."))
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)


class TestImagePromptGeneratorTool:
    def setup_method(self):
        self.tool = ImagePromptGeneratorTool()

    @pytest.mark.parametrize("style", ["modern", "playful", "luxury", "tech"])
    def test_generates_prompt_for_each_style(self, style: str):
        data = json.loads(self.tool._run("A cozy living room", brand_style=style))
        assert "dalle_prompt" in data
        assert "stable_diffusion_prompt" in data
        assert len(data["dalle_prompt"]) > 20

    def test_platform_specs_applied(self):
        data = json.loads(
            self.tool._run("Product hero shot", target_platform="story")
        )
        assert data["platform_specs"]["aspect_ratio"] == "9:16"

    def test_composition_tips_present(self):
        data = json.loads(self.tool._run("Sunset landscape"))
        assert len(data["composition_tips"]) >= 3
