"""Pydantic schemas for Story Intelligence Engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedCharacterSchema(BaseModel):
    character_code: str = Field(..., min_length=1, max_length=32)
    name: str
    role: str
    age_range: str | None = None
    physical_appearance: str
    clothing: str | None = None
    personality: str
    voice_characteristics: str
    relationships: list[dict[str, str]] = Field(default_factory=list)
    emotional_development: str | None = None
    uncertain_details: list[str] = Field(default_factory=list)


class ExtractedLocationSchema(BaseModel):
    location_code: str = Field(..., min_length=1, max_length=32)
    name: str
    description: str
    environment: str | None = None
    lighting_characteristics: str | None = None
    time_of_day: str | None = None
    visual_elements: list[str] = Field(default_factory=list)


class ExtractedNarrativeEventSchema(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=32)
    description: str
    characters: list[str] = Field(default_factory=list)
    location: str | None = None
    timeline_position: int = Field(..., ge=1)
    narrative_role: str
    narrative_importance: float = Field(default=0.7, ge=0.0, le=1.0)
    cause: str | None = None
    consequence: str | None = None
    emotion: str
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    continuity_info: dict[str, Any] = Field(default_factory=dict)


class StoryStructureSchema(BaseModel):
    inciting_incident: str
    rising_action: str
    climax: str
    resolution: str
    pacing_arc: str = "escalating"
    dialogue_present: bool = False


class LLMStoryIntelligencePayload(BaseModel):
    characters: list[ExtractedCharacterSchema] = Field(..., min_length=1)
    locations: list[ExtractedLocationSchema] = Field(..., min_length=1)
    events: list[ExtractedNarrativeEventSchema] = Field(..., min_length=2)
    story_structure: StoryStructureSchema
