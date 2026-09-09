"""Research Agent for gathering market insights and competitor analysis"""

from crewai import Agent

from src.agents.base_agent import BaseAgent, get_llm
from src.tools import CompetitorAnalysisTool, TrendResearchTool


class ResearchAgent(BaseAgent):
    """
    Agent responsible for researching market trends, competitors, and audience insights.
    """
    
    def __init__(self, **kwargs):
        default_config = {
            "name": "Market Research Expert",
            "role": "Market Researcher",
            "goal": "Analyze market trends and competitive landscape to inform campaign strategy",
            "backstory": "You are an expert market researcher with deep knowledge of consumer behavior, "
                        "market trends, and competitive intelligence. You excel at finding actionable insights "
                        "from complex market data.",
        }
        kwargs = {**default_config, **kwargs}
        super().__init__(**kwargs)
    
    def execute(self, task: str) -> str:
        """Execute a research task"""
        # Implementation will use CrewAI framework
        return f"Research completed for: {task}"


def create_research_agent() -> Agent:
    return Agent(
        role="Senior Market Research Analyst",
        goal=(
            "Conduct comprehensive market research including trend analysis, "
            "competitor profiling and audience persona synthesis. Deliver "
            "actionable insights the creative team can build on."
        ),
        backstory=(
            "You have 15 years of experience in market intelligence at top "
            "agencies (Ogilvy, McKinsey). You combine quantitative rigour "
            "with qualitative intuition. You always cite data points and "
            "surface non-obvious opportunities that give campaigns an edge."
        ),
        tools=[TrendResearchTool(), CompetitorAnalysisTool()],
        llm=get_llm(temperature=0.3),
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )
