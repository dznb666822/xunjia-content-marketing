"""Image Prompt Generator Tool.

Builds structured prompts for visual creative direction.
"""

from __future__ import annotations

import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ImagePromptInput(BaseModel):
    concept: str = Field(..., description="Visual concept to describe")
    brand_style: str = Field(default="modern", description="Brand style")
    target_platform: str = Field(
        default="feed", description="Placement (feed, story, banner)"
    )


class ImagePromptGeneratorTool(BaseTool):
    name: str = "image_prompt_generator"
    description: str = (
        "Generate DALL-E and Stable Diffusion prompts plus composition tips."
    )
    args_schema: Type[BaseModel] = ImagePromptInput

    def _run(
        self,
        concept: str,
        brand_style: str = "modern",
        target_platform: str = "feed",
    ) -> str:
        style_map = {
            "modern": "minimalist, clean lines, soft gradients",
            "playful": "bright colors, whimsical shapes, energetic mood",
            "luxury": "moody lighting, rich textures, premium materials",
            "tech": "futuristic, neon accents, sleek surfaces",
        }
        platform_specs = {
            "feed": {"aspect_ratio": "1:1", "resolution": "1080x1080"},
            "story": {"aspect_ratio": "9:16", "resolution": "1080x1920"},
            "banner": {"aspect_ratio": "16:9", "resolution": "1920x1080"},
        }
        style_desc = style_map.get(brand_style, style_map["modern"])
        specs = platform_specs.get(target_platform, platform_specs["feed"])

        dalle_prompt = (
            f"{concept}, {style_desc}, cinematic lighting, "
            f"high detail, commercial photography"
        )
        sd_prompt = (
            f"{concept}, {style_desc}, ultra-detailed, "
            f"studio lighting, shallow depth of field"
        )

        payload = {
            "concept": concept,
            "brand_style": brand_style,
            "platform_specs": specs,
            "dalle_prompt": dalle_prompt,
            "stable_diffusion_prompt": sd_prompt,
            "composition_tips": [
                "Use strong leading lines toward the product.",
                "Keep negative space for headline placement.",
                "Balance subject weight with light and shadow.",
            ],
        }
        return json.dumps(payload, indent=2)
