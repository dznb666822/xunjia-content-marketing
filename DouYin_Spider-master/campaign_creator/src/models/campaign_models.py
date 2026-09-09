"""Pydantic models for campaign data structures"""

import hashlib
import re
import secrets
from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class CampaignChannel(str, Enum):
    """Available campaign channels."""
    SOCIAL_MEDIA = "social_media"
    EMAIL = "email"
    DISPLAY_ADS = "display_ads"
    INFLUENCER = "influencer"
    CONTENT_MARKETING = "content_marketing"
    VIDEO = "video"
    SEARCH_ADS = "search_ads"
    AFFILIATE = "affiliate"


class CopyTone(str, Enum):
    """Available copy tones/brand voices."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    PLAYFUL = "playful"
    LUXURY = "luxury"
    EDUCATIONAL = "educational"
    MOTIVATIONAL = "motivational"
    TECHNICAL = "technical"
    FRIENDLY = "friendly"


class CampaignRequest(BaseModel):
    """Structured request used by agents and workflows."""

    product_name: str = ""
    product_description: str = ""
    target_audience: str = ""
    campaign_goals: str = ""
    budget_range: Optional[str] = None
    channels: List[CampaignChannel] = Field(default_factory=list)
    brand_voice: CopyTone = CopyTone.PROFESSIONAL
    additional_context: Optional[str] = None


class CampaignBrief(BaseModel):
    """Input brief for campaign creation"""

    client_name: str = Field(..., description="Name of the client")
    campaign_name: str = Field(..., description="Name of the campaign")
    objective: str = Field(..., description="Primary campaign objective")
    target_audience: str = Field(..., description="Description of target audience")
    budget: Optional[float] = Field(None, description="Campaign budget")
    timeline: Optional[str] = Field(None, description="Campaign timeline")
    key_messages: List[str] = Field(
        default_factory=list, description="Key messages to convey"
    )
    constraints: Optional[str] = Field(
        None, description="Any constraints or limitations"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    request: Optional[CampaignRequest] = None
    research: Optional["MarketResearch"] = None
    copy_package: Optional["CopyPackage"] = None
    visuals: Optional["VisualDirection"] = None
    executive_summary: str = ""
    implementation_timeline: List[str] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    estimated_budget_allocation: Dict[str, str] = Field(default_factory=dict)
    risk_factors: List[str] = Field(default_factory=list)
    final_recommendations: str = ""


class MarketResearch(BaseModel):
    """Market research output"""
    
    market_summary: str = ""
    trends: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    audience_insights: Dict = Field(default_factory=dict)
    competitive_landscape: Dict = Field(default_factory=dict)


class CopyPackage(BaseModel):
    """Structured copy package for campaign execution."""

    campaign_tagline: str = ""
    elevator_pitch: str = ""
    channel_copy: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    email_subjects: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)


class VisualDirection(BaseModel):
    """Structured visual direction for creative assets."""

    brand_visual_identity: str = ""
    key_visuals: List[str] = Field(default_factory=list)
    image_prompts: List[str] = Field(default_factory=list)


class CreativeOutput(BaseModel):
    """Creative campaign output"""
    
    tagline: str = Field(..., description="Campaign tagline")
    primary_message: str = Field(..., description="Primary campaign message")
    ad_copy_variations: List[str] = Field(default_factory=list)
    visual_concepts: List[str] = Field(default_factory=list)
    image_prompts: List[str] = Field(default_factory=list)


class CampaignOutput(BaseModel):
    """Complete campaign output"""
    
    campaign_id: str = Field(..., description="Unique campaign ID")
    client_name: str = Field(..., description="Client name")
    campaign_name: str = Field(..., description="Campaign name")
    created_at: datetime = Field(default_factory=datetime.now)
    market_research: MarketResearch
    creative_output: CreativeOutput
    overall_strategy: str = Field(..., description="Overall campaign strategy")
    next_steps: List[str] = Field(default_factory=list)


class Campaign(BaseModel):
    """Main campaign model"""
    
    brief: CampaignBrief
    output: Optional[CampaignOutput] = None
    status: str = Field(default="draft", description="Campaign status")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def mark_completed(self):
        """Mark campaign as completed"""
        self.status = "completed"
        self.updated_at = datetime.now()


# ── Run Identity & Metadata (Phase 1: Run Reliability) ───────────────────

class RunID(BaseModel):
    """Immutable run identifier.
    
    Format: UTC_TIMESTAMP-RANDOM_SUFFIX (e.g., "20260415T093045-a7x2m")
    
    D-01, D-02: Immutable ID generated once per campaign run.
    """
    
    value: str = Field(..., description="Run identifier string (format: YYYYMMDDTHHMMSS-xxxxx)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When run ID was generated")
    
    @field_validator("value")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        """Validate RunID format matches pattern YYYYMMDDTHHMMSS-xxxxx"""
        pattern = r"^\d{8}T\d{6}-[a-z0-9]{5}$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid RunID format: '{v}'. Expected pattern: YYYYMMDDTHHMMSS-xxxxx"
            )
        return v
    
    @classmethod
    def generate(cls) -> "RunID":
        """Generate a new immutable RunID.
        
        Creates UUID format: UTC timestamp + 5-char random alphanumeric suffix.
        Uses secrets.token_hex(3) for 6 hex chars, trimmed to 5 for display.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        # secrets.token_hex(3) gives 6 hex chars, we trim to 5
        random_suffix = secrets.token_hex(3)[:5]
        return cls(value=f"{timestamp}-{random_suffix}")
    
    def __hash__(self) -> int:
        """Hash allows RunID to be used as dict key"""
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        """RunIDs are equal when their identifier value matches.

        Consistent with __hash__ (which also keys on value), so a rehydrated
        RunID compares equal to the original regardless of created_at.
        """
        if not isinstance(other, RunID):
            return NotImplemented
        return self.value == other.value

    def __str__(self) -> str:
        """String representation returns the value"""
        return self.value


class RunMetadata(BaseModel):
    """Run execution metadata stored in SQLite.
    
    D-03, D-04: Persisted metadata for run tracking, retry recording, artifact linkage.
    """
    
    run_id: RunID = Field(..., description="The run identifier")
    start_time: datetime = Field(default_factory=datetime.utcnow, description="Workflow start time (UTC)")
    end_time: Optional[datetime] = Field(None, description="Workflow end time (UTC)")
    status: str = Field(default="pending", description="Run status: pending, running, success, failed")
    retry_count: int = Field(default=0, description="Cumulative retries for this run")
    terminal_failure_reason: Optional[str] = Field(None, description="Failure reason if run failed")
    parent_run_id: Optional[RunID] = Field(None, description="Parent run ID for rerun chains (D-08)")
    config_snapshot: Dict = Field(default_factory=dict, description="Serialized CampaignRequest for rerun replay")
    artifacts: List[Dict] = Field(
        default_factory=list,
        description="List of artifacts: {path, content_hash, saved_at}"
    )
    
    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values"""
        allowed = {"pending", "running", "success", "failed"}
        if v not in allowed:
            raise ValueError(f"Invalid status: '{v}'. Must be one of: {allowed}")
        return v
    
    @field_validator("end_time")
    @classmethod
    def _validate_timing(cls, end_time: Optional[datetime], info) -> Optional[datetime]:
        """Validate end_time >= start_time if both present"""
        if end_time is None:
            return end_time
        
        # Get start_time from the model data
        start_time = info.data.get("start_time")
        if start_time and end_time < start_time:
            raise ValueError("end_time cannot be before start_time")
        return end_time
