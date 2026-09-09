"""Manager Agent for overseeing the entire campaign creation process"""

from crewai import Agent

from src.agents.base_agent import BaseAgent, get_llm


class ManagerAgent(BaseAgent):
    """
    Agent responsible for orchestrating and managing the entire campaign workflow.
    """
    
    def __init__(self, **kwargs):
        default_config = {
            "name": "Campaign Manager",
            "role": "Campaign Manager",
            "goal": "Successfully orchestrate the campaign creation process and ensure all deliverables are cohesive",
            "backstory": "You are an experienced campaign manager known for delivering exceptional campaigns on time. "
                        "You excel at coordinating teams, managing timelines, and ensuring all elements work together seamlessly.",
        }
        kwargs = {**default_config, **kwargs}
        super().__init__(**kwargs)
    
    def execute(self, task: str) -> str:
        """Execute a management task"""
        # Implementation will use CrewAI framework
        return f"Campaign managed: {task}"


def create_manager_agent() -> Agent:
    return Agent(
        role="Campaign Strategy Director",
        goal=(
            "Synthesize research, copy, and visuals into a cohesive "
            "campaign plan with clear next steps and KPIs."
        ),
        backstory=(
            "You're a seasoned strategy director who connects the dots "
            "between insights, creative, and execution. You obsess over "
            "clarity, prioritization, and measurable outcomes."
        ),
        llm=get_llm(temperature=0.4),
        verbose=True,
        allow_delegation=False,
        max_iter=4,
    )
