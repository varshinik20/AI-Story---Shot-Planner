"""Pydantic schemas for Story Development Engine."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class GeneratedSuggestionItem(BaseModel):
    """Single creator-controlled enhancement suggestion."""

    section_title: str = Field(..., min_length=1, max_length=255)
    original_passage: str = Field(..., min_length=1)
    suggested_passage: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)


class LLMStoryDevelopmentPayload(BaseModel):
    """Structured story draft and suggestions returned by the LLM."""

    developed_story: str = Field(..., min_length=20)
    beginning_summary: str
    middle_summary: str
    ending_summary: str
    dialogue_present: bool = False
    suggestions: list[GeneratedSuggestionItem] = Field(..., min_length=2, max_length=4)


class StorySuggestionOut(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    section_title: str
    original_passage: str
    suggested_passage: str
    explanation: str
    status: str


class StoryVersionOut(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    version_number: int
    label: str
    content: str
    is_approved: bool


class StoryDetailResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    conversation_id: uuid.UUID | None
    title: str
    visual_style: str | None
    premise: str
    source_type: str
    original_content: str
    working_content: str
    approved_content: str | None
    status: str
    structure_json: dict | None = None
    versions: list[StoryVersionOut] = Field(default_factory=list)
    suggestions: list[StorySuggestionOut] = Field(default_factory=list)


class DevelopStoryRequest(BaseModel):
    project_id: uuid.UUID | None = None
    story_id: uuid.UUID | None = None
    instruction: str | None = None
    preserve_original_text: bool = False


class SuggestionDecisionRequest(BaseModel):
    decision: Literal["accept", "reject"]
    edited_text: str | None = None


class ApproveStoryRequest(BaseModel):
    story_id: uuid.UUID
    edited_content: str | None = None
