"""Progressive one-scene-at-a-time shot generation, editing, and What-If endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.dependencies import AppSettings, DbSession
from app.engines.production import ProductionEngine
from app.engines.production.schemas import GenerateShotsRequest, SceneOut, UpdateShotRequest
from app.engines.what_if import WhatIfEngine
from app.services.llm_service import LLMService

router = APIRouter(prefix="/shots", tags=["shots"])


class AlternativesRequest(BaseModel):
    creative_prompt: str | None = None


@router.post(
    "/generate",
    response_model=SceneOut,
    status_code=status.HTTP_200_OK,
    summary="Generate shots strictly for one approved scene using accumulated continuity state",
)
async def generate_shots_for_scene(
    payload: GenerateShotsRequest,
    session: DbSession,
    settings: AppSettings,
) -> SceneOut:
    llm = LLMService(session=session, settings=settings)
    engine = ProductionEngine(session=session, settings=settings, llm_service=llm)
    return await engine.generate_shots_for_scene(scene_uuid=payload.scene_uuid)


@router.patch(
    "/{shot_uuid}",
    status_code=status.HTTP_200_OK,
    summary="Directly edit an individual shot's framing, camera, dialogue, duration, or sound",
)
async def update_shot(
    shot_uuid: uuid.UUID,
    payload: UpdateShotRequest,
    session: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    llm = LLMService(session=session, settings=settings)
    engine = ProductionEngine(session=session, settings=settings, llm_service=llm)
    return await engine.update_shot(
        shot_uuid=shot_uuid,
        updates=payload.model_dump(exclude_unset=True),
    )


@router.post(
    "/{shot_uuid}/alternatives",
    status_code=status.HTTP_200_OK,
    summary="Generate 3 What-If cinematic treatment alternatives for a single shot",
)
async def generate_shot_alternatives(
    shot_uuid: uuid.UUID,
    payload: AlternativesRequest,
    session: DbSession,
    settings: AppSettings,
) -> list[dict[str, Any]]:
    llm = LLMService(session=session, settings=settings)
    engine = WhatIfEngine(session=session, settings=settings, llm_service=llm)
    return await engine.generate_alternatives(
        shot_uuid=shot_uuid,
        creative_prompt=payload.creative_prompt,
    )


@router.post(
    "/{shot_uuid}/alternatives/{alt_id}/apply",
    status_code=status.HTTP_200_OK,
    summary="Apply a selected What-If treatment to a single shot without regenerating other scenes",
)
async def apply_shot_alternative(
    shot_uuid: uuid.UUID,
    alt_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    llm = LLMService(session=session, settings=settings)
    engine = WhatIfEngine(session=session, settings=settings, llm_service=llm)
    return await engine.apply_alternative(shot_uuid=shot_uuid, alternative_id=alt_id)
