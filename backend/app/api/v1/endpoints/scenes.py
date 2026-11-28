"""Progressive scene breakdown and approval endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies import AppSettings, DbSession
from app.engines.production import ProductionEngine
from app.engines.production.schemas import ApproveScenesRequest, GenerateScenesRequest, SceneOut
from app.services.llm_service import LLMService

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.post(
    "/generate",
    response_model=list[SceneOut],
    status_code=status.HTTP_200_OK,
    summary="Generate scene breakdown proposal from narrative graph without generating shots yet",
)
async def generate_scenes(
    payload: GenerateScenesRequest,
    session: DbSession,
    settings: AppSettings,
) -> list[SceneOut]:
    llm = LLMService(session=session, settings=settings)
    engine = ProductionEngine(session=session, settings=settings, llm_service=llm)
    return await engine.generate_scenes(
        project_id=payload.project_id,
        approve_immediately=payload.approve_immediately,
    )


@router.post(
    "/approve",
    response_model=list[SceneOut],
    status_code=status.HTTP_200_OK,
    summary="Approve proposed scenes so progressive shot generation can proceed",
)
async def approve_scenes(
    payload: ApproveScenesRequest,
    session: DbSession,
    settings: AppSettings,
) -> list[SceneOut]:
    llm = LLMService(session=session, settings=settings)
    engine = ProductionEngine(session=session, settings=settings, llm_service=llm)
    return await engine.approve_scenes(
        project_id=payload.project_id,
        scene_ids=payload.scene_ids,
        approve_all=payload.approve_all,
    )


@router.get(
    "/{project_id}",
    response_model=list[SceneOut],
    status_code=status.HTTP_200_OK,
    summary="List scenes and nested shots for a project",
)
async def list_project_scenes(
    project_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
) -> list[SceneOut]:
    llm = LLMService(session=session, settings=settings)
    engine = ProductionEngine(session=session, settings=settings, llm_service=llm)
    return await engine.list_scenes(project_id)
