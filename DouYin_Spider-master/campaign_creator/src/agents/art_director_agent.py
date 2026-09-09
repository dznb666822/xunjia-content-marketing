"""Art Director Agent for creative visual direction and concepts"""

from crewai import Agent

from src.agents.base_agent import BaseAgent, get_llm
from src.tools import ImagePromptGeneratorTool


class ArtDirectorAgent(BaseAgent):
    """
    Agent responsible for visual direction and creative concepts.
    """
    
    def __init__(self, **kwargs):
        default_config = {
            "name": "Senior Art Director",
            "role": "Art Director",
            "goal": "Develop compelling visual concepts and creative direction for the campaign",
            "backstory": "You are a visionary art director with expertise in visual storytelling and brand aesthetics. "
                        "You excel at translating concepts into striking visual experiences that capture attention.",
        }
        kwargs = {**default_config, **kwargs}
        super().__init__(**kwargs)
    
    def execute(self, task: str) -> str:
        """Execute an art direction task"""
        # Implementation will use CrewAI framework
        return f"Visual direction created for: {task}"


def create_art_director_agent() -> Agent:
    return Agent(
        role="Senior Art Director",
        goal=(
            "Translate strategy into visual systems and storytelling that "
            "feel premium, modern, and memorable."
        ),
        backstory=(
            "You have led global brand systems for luxury and tech brands. "
            "You turn abstract ideas into striking visual concepts and are "
            "obsessed with detail and composition."
        ),
        tools=[ImagePromptGeneratorTool()],
        llm=get_llm(temperature=0.6),
        verbose=True,
        allow_delegation=False,
        max_iter=4,
    )
