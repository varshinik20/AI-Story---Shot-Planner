"""Pydantic schemas for Progressive Scene & Shot Production Engine."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ProposedSceneItem(BaseModel):
    scene_id: str
    scene_order: int = Field(..., ge=1)
    title: str
    location: str
    time_of_day: str
    summary: str
    event_ids: list[str] = Field(default_factory=list)


class LLMSceneBreakdownPayload(BaseModel):
    scenes: list[ProposedSceneItem] = Field(..., min_length=1)


class CameraSpec(BaseModel):
    angle: str
    movement: str


class DialogueLineSpec(BaseModel):
    speaker: str
    exact_line: str
    delivery: str


class ProducedShotItem(BaseModel):
    shot_id: str
    shot_order: int = Field(..., ge=1)
    duration_seconds: int = Field(..., ge=1, le=60)
    framing: str
    camera: CameraSpec
    characters: list[str] = Field(default_factory=list)
    location: str
    visual_description: str
    dialogue: list[DialogueLineSpec] = Field(default_factory=list)
    emotion: str
    sound: str


class LLMSceneShotsPayload(BaseModel):
    shots: list[ProducedShotItem] = Field(..., min_length=1, max_length=40)


class GenerateScenesRequest(BaseModel):
    project_id: uuid.UUID
    approve_immediately: bool = False


class ApproveScenesRequest(BaseModel):
    project_id: uuid.UUID
    scene_ids: list[uuid.UUID] | None = None
    approve_all: bool = False


class GenerateShotsRequest(BaseModel):
    scene_uuid: uuid.UUID


class UpdateShotRequest(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=1, le=60)
    framing: str | None = None
    camera: dict[str, str] | None = None
    characters: list[str] | None = None
    location: str | None = None
    visual_description: str | None = None
    dialogue: list[dict[str, str]] | None = None
    emotion: str | None = None
    sound: str | None = None


class SceneOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    scene_id: str
    scene_order: int
    title: str
    location: str
    time_of_day: str
    summary: str
    event_ids: list[str]
    is_approved: bool
    shots_generated: bool
    shots: list[dict[str, Any]] = Field(default_factory=list)
