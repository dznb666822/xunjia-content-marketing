"""Tests for workflow orchestration"""

import pytest
import src.workflow.crew_workflow as crew_workflow
from src.workflow import CampaignCrew
from src.models import CampaignRequest, CampaignChannel, CopyTone


class TestCampaignCrew:
    """Test Campaign Crew orchestration"""
    
    def test_crew_initialization_with_request(self):
        """Test that crew initializes with a campaign request"""
        request = CampaignRequest(
            product_name="Test Product",
            product_description="Test description",
            target_audience="Test audience",
            campaign_goals="Test goals",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        crew = CampaignCrew(request)
        assert crew.request is not None
        assert crew.researcher is not None
        assert crew.copywriter is not None
        assert crew.art_director is not None
        assert crew.manager is not None
    
    def test_crew_has_all_agents(self):
        """Test that crew initializes with all four agents"""
        request = CampaignRequest(
            product_name="Test Product",
            product_description="Test description",
            target_audience="Test audience",
            campaign_goals="Test goals",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        crew = CampaignCrew(request)
        
        assert crew.researcher is not None
        assert crew.copywriter is not None
        assert crew.art_director is not None
        assert crew.manager is not None
    
    def test_crew_builds_tasks(self):
        """Test that crew properly builds tasks"""
        request = CampaignRequest(
            product_name="Test Product",
            product_description="Test description",
            target_audience="Test audience",
            campaign_goals="Test goals",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        crew = CampaignCrew(request)
        
        assert crew.research_task is not None
        assert crew.copy_task is not None
        assert crew.art_task is not None
        assert crew.manager_task is not None

    def test_run_retries_rate_limit_then_succeeds(self, monkeypatch):
        """Run should retry a transient 429 and continue successfully."""
        request = CampaignRequest(
            product_name="Test Product",
            product_description="Test description",
            target_audience="Test audience",
            campaign_goals="Test goals",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        crew = CampaignCrew(request)

        class _Settings:
            groq_rate_limit_retries = 2
            groq_retry_base_seconds = 1.0
            groq_retry_max_seconds = 10.0

        monkeypatch.setattr(crew_workflow, "settings", _Settings())

        sleeps = []
        monkeypatch.setattr(crew_workflow.time, "sleep", lambda s: sleeps.append(s))
        monkeypatch.setattr(crew, "_save_outputs", lambda brief, raw: None)

        calls = {"count": 0}

        def _kickoff():
            calls["count"] += 1
            if calls["count"] == 1:
                raise Exception("Rate limit reached. Please try again in 0.25s")
            return "ok campaign output"

        monkeypatch.setattr(type(crew.crew), "kickoff", lambda _self: _kickoff())

        brief = crew.run()

        assert brief is not None
        assert calls["count"] == 2
        assert sleeps == [0.25]

    def test_run_raises_after_retry_exhaustion(self, monkeypatch):
        """Run should re-raise rate-limit errors once retries are exhausted."""
        request = CampaignRequest(
            product_name="Test Product",
            product_description="Test description",
            target_audience="Test audience",
            campaign_goals="Test goals",
            channels=[CampaignChannel.SOCIAL_MEDIA],
            brand_voice=CopyTone.PROFESSIONAL,
        )
        crew = CampaignCrew(request)

        class _Settings:
            groq_rate_limit_retries = 1
            groq_retry_base_seconds = 1.0
            groq_retry_max_seconds = 3.0

        monkeypatch.setattr(crew_workflow, "settings", _Settings())

        sleeps = []
        monkeypatch.setattr(crew_workflow.time, "sleep", lambda s: sleeps.append(s))

        monkeypatch.setattr(
            type(crew.crew),
            "kickoff",
            lambda _self: (_ for _ in ()).throw(Exception("429 Too Many Requests")),
        )

        with pytest.raises(Exception, match="429 Too Many Requests"):
            crew.run()

        assert sleeps == [1.0]

