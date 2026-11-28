"""Pydantic schemas for Creative Direction Engine."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class CreativeIntentData(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    visual_style: str | None = None
    overall_mood: str | None = None
    pacing: str | None = None
    lighting: str | None = None
    camera_preferences: str | None = None
    audience_experience: str | None = None
    ending_tone: str | None = None
    interview_answers: dict[str, Any] = Field(default_factory=dict)
    pending_questions: list[str] = Field(default_factory=list)
    is_complete: bool = False


class LLMIntentInterviewPayload(BaseModel):
    """LLM response mapping creator intent + next natural question."""

    visual_style: str | None = None
    overall_mood: str | None = None
    pacing: str | None = None
    lighting: str | None = None
    camera_preferences: str | None = None
    audience_experience: str | None = None
    ending_tone: str | None = None
    next_question: str
    quick_options: list[str] = Field(default_factory=list)
    target_dimension: str | None = None


class IntentInterviewRequest(BaseModel):
    project_id: uuid.UUID
    story_id: uuid.UUID | None = None


class IntentAnswerRequest(BaseModel):
    project_id: uuid.UUID
    answer: str | None = None
    updates: dict[str, str] | None = None
    confirm: bool = False


class IntentInterviewResponse(BaseModel):
    project_id: uuid.UUID
    creative_intent: CreativeIntentData
    missing_dimensions: list[str]
    is_complete: bool
    next_question: str | None
    quick_options: list[str] = Field(default_factory=list)
    target_dimension: str | None = None
