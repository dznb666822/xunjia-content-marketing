"""Campaign-specific task definitions"""

from enum import Enum
from pydantic import BaseModel, Field
from crewai import Task

from src.models import CampaignRequest


class TaskType(str, Enum):
    """Enumeration of task types"""
    MARKET_RESEARCH = "market_research"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    COPYWRITING = "copywriting"
    VISUAL_DIRECTION = "visual_direction"
    CAMPAIGN_STRATEGY = "campaign_strategy"


class CampaignTask(BaseModel):
    """Base model for campaign tasks"""
    
    task_type: TaskType = Field(..., description="Type of task")
    description: str = Field(..., description="Detailed task description")
    priority: int = Field(default=1, ge=1, le=5, description="Priority level (1-5)")
    expected_output: str = Field(..., description="Expected output format/content")


class CampaignTasks:
    """Container for campaign-related tasks"""
    
    @staticmethod
    def create_research_task(campaign_brief: str) -> CampaignTask:
        """Create a market research task"""
        return CampaignTask(
            task_type=TaskType.MARKET_RESEARCH,
            description=f"Research market trends and insights for: {campaign_brief}",
            priority=1,
            expected_output="Market research report with trends, opportunities, and target audience insights"
        )
    
    @staticmethod
    def create_competitor_analysis_task(campaign_brief: str) -> CampaignTask:
        """Create a competitor analysis task"""
        return CampaignTask(
            task_type=TaskType.COMPETITOR_ANALYSIS,
            description=f"Analyze competitors in the space for: {campaign_brief}",
            priority=1,
            expected_output="Competitor analysis with strengths, weaknesses, and differentiation opportunities"
        )
    
    @staticmethod
    def create_copywriting_task(research_insights: str) -> CampaignTask:
        """Create a copywriting task"""
        return CampaignTask(
            task_type=TaskType.COPYWRITING,
            description=f"Create compelling copy based on: {research_insights}",
            priority=2,
            expected_output="Primary messaging, taglines, and ad copy variations"
        )
    
    @staticmethod
    def create_visual_direction_task(campaign_brief: str) -> CampaignTask:
        """Create a visual direction task"""
        return CampaignTask(
            task_type=TaskType.VISUAL_DIRECTION,
            description=f"Develop visual direction for: {campaign_brief}",
            priority=2,
            expected_output="Visual concepts, mood boards, color palettes, and creative prompts"
        )


class CampaignTaskFactory:
    """Factory for CrewAI Task objects wired with dependencies."""

    # Appended to the final-stage task when a non-empty output_language is given.
    LANGUAGE_INSTRUCTION = (
        "\n\n**Output language:** Write the ENTIRE brief in {language}. "
        "Keep product names, brand names and widely-used marketing terms "
        "as-is; translate everything else naturally and idiomatically.\n"
    )

    def __init__(self, request: CampaignRequest, output_language: str = ""):
        self.request = request
        self.output_language = output_language

    def research_task(self, agent) -> Task:
        return Task(
            description=(
                f"Conduct thorough market research for: **{self.request.product_name}**\n\n"
                f"**Product:** {self.request.product_name}\n"
                f"**Target audience:** {self.request.target_audience}\n"
                f"**Campaign goals:** {self.request.campaign_goals}\n"
                f"**Channels:** {', '.join(c.value for c in self.request.channels)}\n\n"
                "Your deliverables:\n"
                "1. Identify 4-6 current market trends relevant to this product.\n"
                "2. Analyse 3 key competitors — positioning, strengths, weaknesses.\n"
                "3. Build 2 detailed audience personas.\n"
                "4. Summarise market opportunities and recommend 3 campaign angles.\n"
            ),
            expected_output="Markdown report with trends, competitors, personas, angles",
            agent=agent,
        )

    def copywriting_task(self, agent, research_task: Task) -> Task:
        return Task(
            description=(
                f"Write compelling ad copy for **{self.request.product_name}**.\n\n"
                f"**Brand voice:** {self.request.brand_voice.value}\n"
                f"**Target audience:** {self.request.target_audience}\n"
                f"**Channels:** {', '.join(c.value for c in self.request.channels)}\n"
                f"**Campaign goals:** {self.request.campaign_goals}\n\n"
                "Deliverables:\n"
                "1. One overarching campaign tagline.\n"
                "2. A 2-sentence elevator pitch.\n"
                "3. For EACH channel — headline, sub-headline, body copy, CTA.\n"
                "4. 5 email subject-line options.\n"
                "5. 5-8 hashtag suggestions.\n"
            ),
            expected_output="Copy package with taglines, channel copy, hashtags",
            agent=agent,
            context=[research_task],
        )

    def art_direction_task(self, agent, research_task: Task, copy_task: Task) -> Task:
        return Task(
            description=(
                f"Create the visual direction for **{self.request.product_name}**.\n\n"
                f"**Target audience:** {self.request.target_audience}\n"
                f"**Channels:** {', '.join(c.value for c in self.request.channels)}\n\n"
                "Deliverables:\n"
                "1. Visual identity and moodboard notes.\n"
                "2. 3 key visual concepts.\n"
                "3. Image generation prompts for each concept.\n"
            ),
            expected_output="Visual direction and prompts",
            agent=agent,
            context=[research_task, copy_task],
        )

    def manager_task(
        self, agent, research_task: Task, copy_task: Task, art_task: Task
    ) -> Task:
        language_note = (
            self.LANGUAGE_INSTRUCTION.format(language=self.output_language)
            if self.output_language
            else ""
        )
        return Task(
            description=(
                f"Assemble the final campaign brief for **{self.request.product_name}**.\n\n"
                "Deliverables:\n"
                "1. Executive summary.\n"
                "2. Integrated strategy across channels.\n"
                "3. 30-day implementation timeline.\n"
                "4. Success metrics and KPIs.\n"
                f"{language_note}"
            ),
            expected_output=(
                "Final campaign brief in markdown"
                + (f", written entirely in {self.output_language}" if self.output_language else "")
            ),
            agent=agent,
            context=[research_task, copy_task, art_task],
        )
