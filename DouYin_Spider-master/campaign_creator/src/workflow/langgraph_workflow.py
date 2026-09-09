"""
LangGraph orchestration for the campaign pipeline.

This module wraps the existing CrewAI agents in a LangGraph state machine.
The division of labour mirrors how production agentic systems are built:

    * **LangGraph** owns the *control flow* — which agent runs next, how state
      is threaded between stages, and where the pipeline halts on failure.
    * **CrewAI** owns the *execution* — each node runs a single CrewAI ``Agent``
      inside a one-task ``Crew`` and returns its output as text.

Unlike ``CampaignCrew`` (which hands the whole pipeline to ``Crew.kickoff()``
and lets CrewAI sequence the tasks internally), here each stage is an explicit
graph node. Upstream outputs are injected into the next node's task description,
so the agents stay decoupled and the routing is visible and testable.

Public API::

    from src.workflow.langgraph_workflow import run_campaign_with_langgraph
    final_state = run_campaign_with_langgraph(request)
    print(final_state["final_brief"])
"""

from __future__ import annotations

from typing import TypedDict

from crewai import Crew, Process, Task
from langgraph.graph import END, StateGraph

from src.agents import (
    create_art_director_agent,
    create_copywriter_agent,
    create_manager_agent,
    create_research_agent,
)
from src.models.campaign_models import CampaignRequest


# ── State definition ─────────────────────────────────────────────────────────
class CampaignState(TypedDict):
    """State threaded through the graph. Each node reads and extends it."""

    request: CampaignRequest
    research_output: str
    copy_output: str
    visual_output: str
    final_brief: str
    current_stage: str
    errors: list[str]
    output_language: str  # e.g. "简体中文"; empty → default (English)


# ── CrewAI execution helper ──────────────────────────────────────────────────
def _run_agent(agent, description: str, expected_output: str) -> str:
    """Run a single CrewAI agent on one task and return its text output.

    Each node gets its own single-task crew. This is what lets LangGraph,
    rather than CrewAI's internal sequencer, decide what runs next.
    """
    task = Task(description=description, expected_output=expected_output, agent=agent)
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    return str(crew.kickoff())


def _channels(request: CampaignRequest) -> str:
    return ", ".join(c.value for c in request.channels)


def _safe_stage_error(stage: str, exc: Exception) -> str:
    """User-facing stage error that avoids leaking provider/internal detail.

    The exception type is kept for triage; the raw message (which may contain
    backend or credential hints) is not surfaced into shared state.
    """
    return f"{stage}: stage failed ({exc.__class__.__name__})"


# ── Node functions (each calls one CrewAI agent) ─────────────────────────────
def run_research(state: CampaignState) -> CampaignState:
    request = state["request"]
    description = (
        f"Conduct thorough market research for **{request.product_name}**.\n\n"
        f"**Product:** {request.product_description}\n"
        f"**Target audience:** {request.target_audience}\n"
        f"**Campaign goals:** {request.campaign_goals}\n"
        f"**Channels:** {_channels(request)}\n\n"
        "Deliver: 4-6 market trends, 3 competitor profiles, 2 audience "
        "personas, and 3 recommended campaign angles."
    )
    try:
        result = _run_agent(
            create_research_agent(),
            description,
            "Markdown report with trends, competitors, personas, angles",
        )
    except Exception as exc:  # noqa: BLE001 - surface failure into state
        return {**state, "errors": [*state["errors"], _safe_stage_error("research", exc)]}
    return {**state, "research_output": result, "current_stage": "research_complete"}


def run_copywriter(state: CampaignState) -> CampaignState:
    request = state["request"]
    description = (
        f"Write compelling ad copy for **{request.product_name}**.\n\n"
        f"**Brand voice:** {request.brand_voice.value}\n"
        f"**Target audience:** {request.target_audience}\n"
        f"**Channels:** {_channels(request)}\n"
        f"**Campaign goals:** {request.campaign_goals}\n\n"
        "## Upstream research to build on\n"
        f"{state['research_output']}\n\n"
        "Deliver: one campaign tagline, a 2-sentence elevator pitch, "
        "per-channel headline/sub-headline/body/CTA, 5 email subject lines, "
        "and 5-8 hashtags."
    )
    try:
        result = _run_agent(
            create_copywriter_agent(),
            description,
            "Copy package with taglines, channel copy, hashtags",
        )
    except Exception as exc:  # noqa: BLE001
        return {**state, "errors": [*state["errors"], _safe_stage_error("copywriter", exc)]}
    return {**state, "copy_output": result, "current_stage": "copy_complete"}


def run_art_director(state: CampaignState) -> CampaignState:
    request = state["request"]
    description = (
        f"Create the visual direction for **{request.product_name}**.\n\n"
        f"**Target audience:** {request.target_audience}\n"
        f"**Channels:** {_channels(request)}\n\n"
        "## Upstream research\n"
        f"{state['research_output']}\n\n"
        "## Approved copy\n"
        f"{state['copy_output']}\n\n"
        "Deliver: visual identity/moodboard notes, 3 key visual concepts, "
        "and an image-generation prompt for each concept."
    )
    try:
        result = _run_agent(
            create_art_director_agent(),
            description,
            "Visual direction and prompts",
        )
    except Exception as exc:  # noqa: BLE001
        return {**state, "errors": [*state["errors"], _safe_stage_error("art_director", exc)]}
    return {**state, "visual_output": result, "current_stage": "visual_complete"}


def run_manager(state: CampaignState) -> CampaignState:
    request = state["request"]
    language = state.get("output_language", "")
    language_note = (
        f"\n\n**Output language:** Write the ENTIRE brief in {language}. "
        "Keep product names, brand names and widely-used marketing terms "
        "as-is; translate everything else naturally and idiomatically.\n"
        if language
        else ""
    )
    description = (
        f"Assemble the final campaign brief for **{request.product_name}**.\n\n"
        "## Research\n"
        f"{state['research_output']}\n\n"
        "## Copy\n"
        f"{state['copy_output']}\n\n"
        "## Visual direction\n"
        f"{state['visual_output']}\n\n"
        "Deliver: executive summary, integrated cross-channel strategy, "
        "a 30-day implementation timeline, and success metrics/KPIs."
        f"{language_note}"
    )
    try:
        result = _run_agent(
            create_manager_agent(),
            description,
            "Final campaign brief in markdown",
        )
    except Exception as exc:  # noqa: BLE001
        return {**state, "errors": [*state["errors"], _safe_stage_error("manager", exc)]}
    return {**state, "final_brief": result, "current_stage": "complete"}


# ── Conditional routing — gate between stages, halt on error ─────────────────
_NEXT_STAGE = {
    "research_complete": "copywriter",
    "copy_complete": "art_director",
    "visual_complete": "manager",
}


def should_continue(state: CampaignState) -> str:
    """Route to the next node, or END if a stage recorded an error."""
    if state.get("errors"):
        return END
    return _NEXT_STAGE.get(state.get("current_stage", ""), END)


# ── Build the graph ──────────────────────────────────────────────────────────
def build_campaign_graph():
    """Compile and return the campaign state graph."""
    graph = StateGraph(CampaignState)

    graph.add_node("research", run_research)
    graph.add_node("copywriter", run_copywriter)
    graph.add_node("art_director", run_art_director)
    graph.add_node("manager", run_manager)

    graph.set_entry_point("research")

    # State-aware routing: each stage either advances or halts on error.
    graph.add_conditional_edges(
        "research", should_continue, {"copywriter": "copywriter", END: END}
    )
    graph.add_conditional_edges(
        "copywriter", should_continue, {"art_director": "art_director", END: END}
    )
    graph.add_conditional_edges(
        "art_director", should_continue, {"manager": "manager", END: END}
    )
    graph.add_edge("manager", END)

    return graph.compile()


def _initial_state(request: CampaignRequest, output_language: str = "") -> CampaignState:
    return CampaignState(
        request=request,
        research_output="",
        copy_output="",
        visual_output="",
        final_brief="",
        current_stage="start",
        errors=[],
        output_language=output_language,
    )


# ── Public API ───────────────────────────────────────────────────────────────
def run_campaign_with_langgraph(request: CampaignRequest) -> CampaignState:
    """Run the full campaign pipeline through the LangGraph state machine.

    Returns the final state. On success ``current_stage == "complete"`` and
    ``final_brief`` holds the assembled brief; on failure ``errors`` is
    populated and the pipeline halts at the failing stage.
    """
    graph = build_campaign_graph()
    return graph.invoke(_initial_state(request))
