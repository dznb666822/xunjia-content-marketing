"""Copywriter Agent for creating compelling marketing content"""

from crewai import Agent

from src.agents.base_agent import BaseAgent, get_llm
from src.tools import CopyEvaluationTool


class CopywriterAgent(BaseAgent):
    """
    Agent responsible for writing persuasive and engaging marketing copy.
    """
    
    def __init__(self, **kwargs):
        default_config = {
            "name": "Creative Copywriter",
            "role": "Copywriter",
            "goal": "Create compelling and persuasive marketing copy that resonates with the target audience",
            "backstory": "You are an award-winning copywriter with a flair for creating memorable messaging. "
                        "You understand the psychology of persuasion and can craft copy that drives action.",
        }
        kwargs = {**default_config, **kwargs}
        super().__init__(**kwargs)
    
    def execute(self, task: str) -> str:
        """Execute a copywriting task"""
        # Implementation will use CrewAI framework
        return f"Copy created for: {task}"


def create_copywriter_agent() -> Agent:
    return Agent(
        role="Senior Creative Copywriter",
        goal=(
            "Craft persuasive and emotionally resonant copy that aligns "
            "with the brand voice while maximising conversion."
        ),
        backstory=(
            "You're a multi-award-winning copywriter who has crafted campaigns "
            "for Apple, Nike, and Airbnb. You obsess over clarity, rhythm, and "
            "calls-to-action."
        ),
        tools=[CopyEvaluationTool()],
        llm=get_llm(temperature=0.7),
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )
