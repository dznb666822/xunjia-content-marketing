"""Agent definitions for the campaign creation workflow"""

from src.agents.base_agent import BaseAgent
from src.agents.research_agent import ResearchAgent, create_research_agent
from src.agents.copywriter_agent import CopywriterAgent, create_copywriter_agent
from src.agents.art_director_agent import ArtDirectorAgent, create_art_director_agent
from src.agents.manager_agent import ManagerAgent, create_manager_agent

__all__ = [
    "BaseAgent",
    "ResearchAgent",
    "CopywriterAgent",
    "ArtDirectorAgent",
    "ManagerAgent",
    "create_research_agent",
    "create_copywriter_agent",
    "create_art_director_agent",
    "create_manager_agent",
]
