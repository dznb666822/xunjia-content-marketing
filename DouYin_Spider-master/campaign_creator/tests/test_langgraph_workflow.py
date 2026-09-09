"""Tests for the LangGraph orchestration layer.

These tests are hermetic: ``_run_agent`` (the only thing that would make a
real CrewAI/LLM call) is monkeypatched, so the graph's structure, routing,
and error-gating are exercised without any network access.
"""

import pytest

import src.workflow.langgraph_workflow as lgw
from src.models import CampaignChannel, CampaignRequest, CopyTone
from src.workflow.langgraph_workflow import (
    CampaignState,
    build_campaign_graph,
    run_campaign_with_langgraph,
    should_continue,
)


@pytest.fixture
def request_obj() -> CampaignRequest:
    return CampaignRequest(
        product_name="AeroFlow Pro",
        product_description="An AI-powered air purifier for smart homes",
        target_audience="Urban millennials",
        campaign_goals="Drive 10,000 pre-orders in 60 days",
        channels=[CampaignChannel.SOCIAL_MEDIA, CampaignChannel.EMAIL],
        brand_voice=CopyTone.PROFESSIONAL,
    )


@pytest.fixture
def stub_agents(monkeypatch):
    """Replace the CrewAI execution helper with a deterministic stub."""
    calls: list[str] = []

    def fake_run_agent(agent, description, expected_output):
        # Identify the stage from the expected_output the node requested.
        stage = expected_output.split()[0].lower()
        calls.append(expected_output)
        return f"[{stage}] output"

    monkeypatch.setattr(lgw, "_run_agent", fake_run_agent)
    return calls


# ── Structure ────────────────────────────────────────────────────────────────
def test_graph_compiles():
    graph = build_campaign_graph()
    assert graph is not None


def test_graph_has_all_four_nodes():
    graph = build_campaign_graph()
    nodes = set(graph.get_graph().nodes)
    for node in ("research", "copywriter", "art_director", "manager"):
        assert node in nodes


def test_initial_state_structure():
    state = CampaignState(
        request=None,
        research_output="",
        copy_output="",
        visual_output="",
        final_brief="",
        current_stage="start",
        errors=[],
    )
    assert state["current_stage"] == "start"
    assert state["errors"] == []


# ── Routing ──────────────────────────────────────────────────────────────────
def test_should_continue_advances_through_stages():
    base = {"errors": []}
    assert should_continue({**base, "current_stage": "research_complete"}) == "copywriter"
    assert should_continue({**base, "current_stage": "copy_complete"}) == "art_director"
    assert should_continue({**base, "current_stage": "visual_complete"}) == "manager"


def test_should_continue_halts_on_error():
    from langgraph.graph import END

    state = {"current_stage": "research_complete", "errors": ["research: boom"]}
    assert should_continue(state) == END


# ── Execution (mocked agents) ────────────────────────────────────────────────
def test_full_pipeline_runs_to_completion(request_obj, stub_agents):
    final = run_campaign_with_langgraph(request_obj)
    assert final["current_stage"] == "complete"
    assert final["final_brief"]
    assert final["research_output"]
    assert final["copy_output"]
    assert final["visual_output"]
    assert final["errors"] == []
    # All four agents were invoked exactly once.
    assert len(stub_agents) == 4


def test_pipeline_halts_when_research_fails(request_obj, monkeypatch):
    def boom(agent, description, expected_output):
        raise RuntimeError("provider down")

    monkeypatch.setattr(lgw, "_run_agent", boom)

    final = run_campaign_with_langgraph(request_obj)
    assert final["errors"]
    assert "research" in final["errors"][0]
    # Downstream stages never ran.
    assert final["copy_output"] == ""
    assert final["final_brief"] == ""
