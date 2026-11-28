"""Pydantic schemas for Adaptive Story Intake."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

InputSourceType = Literal["text", "voice", "document"]


class IntakeState(BaseModel):
    """Structured creative intake state persisted per conversation."""

    story_title: str | None = None
    title_confirmed: bool = False
    visual_style: str | None = None
    story_context: str | None = None
    dialogue_source: str | None = None
    confirmed_by_creator: bool = False
    awaiting_confirmation: bool = False
    suggested_titles: list[str] = Field(default_factory=list)
    input_sources_seen: list[str] = Field(default_factory=list)
    extracted_from_filename: str | None = None
    current_stage: str = "awaiting_title"
    confirmation_status: str = "not_confirmed"
    generation_status: str = "not_started"
    last_assistant_question: str | None = None
    updated_at: str | None = None

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.story_title or not self.story_title.strip():
            missing.append("story_title")
        if not self.visual_style or not self.visual_style.strip():
            missing.append("visual_style")
        if not self.story_context or not self.story_context.strip():
            missing.append("story_context")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


class LLMIntakeExtractionPayload(BaseModel):
    """Structured JSON returned by the LLM intake analyzer."""

    intent: Literal[
        "story_creation",
        "provide_details",
        "request_title_suggestion",
        "request_style_suggestion",
        "confirm_intake",
        "edit_details",
        "general_chat",
    ] = "story_creation"
    extracted_story_title: str | None = None
    explicit_title_provided: bool = False
    extracted_visual_style: str | None = None
    extracted_story_context: str | None = None
    extracted_dialogue_source: str | None = None
    is_confirming: bool = False
    requests_title_suggestions: bool = False
    requests_style_suggestions: bool = False
    suggested_titles: list[str] = Field(default_factory=list)
    natural_response: str


class IntakeAnalysisResult(BaseModel):
    """Result returned by StoryIntakeEngine."""

    intent: str
    intake_state: IntakeState
    missing_fields: list[str]
    next_question_field: str | None
    ready_for_story_development: bool
    needs_confirmation: bool
    assistant_message: str
    suggested_titles: list[str] = Field(default_factory=list)
    style_options: list[str] = Field(default_factory=list)
