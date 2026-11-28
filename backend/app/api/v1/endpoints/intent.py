"""Creative direction / adaptive interview endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies import AppSettings, DbSession
from app.engines.creative_direction import CreativeDirectionEngine
from app.engines.creative_direction.schemas import (
    IntentAnswerRequest,
    IntentInterviewRequest,
    IntentInterviewResponse,
)
from app.services.llm_service import LLMService

router = APIRouter(prefix="/intent", tags=["intent"])


@router.post(
    "/interview",
    response_model=IntentInterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Start or continue the adaptive creative direction interview",
)
async def interview_creative_intent(
    payload: IntentInterviewRequest,
    session: DbSession,
    settings: AppSettings,
) -> IntentInterviewResponse:
    llm = LLMService(session=session, settings=settings)
    engine = CreativeDirectionEngine(session=session, llm_service=llm)
    return await engine.run_interview(project_id=payload.project_id, story_id=payload.story_id)


@router.post(
    "/answer",
    response_model=IntentInterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit an adaptive interview answer or edit creative direction fields",
)
async def answer_creative_intent(
    payload: IntentAnswerRequest,
    session: DbSession,
    settings: AppSettings,
) -> IntentInterviewResponse:
    llm = LLMService(session=session, settings=settings)
    engine = CreativeDirectionEngine(session=session, llm_service=llm)
    return await engine.submit_answer(
        project_id=payload.project_id,
        answer=payload.answer,
        updates=payload.updates,
        confirm=payload.confirm,
    )


@router.get(
    "/{project_id}",
    response_model=IntentInterviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current CreativeIntent state for a project",
)
async def get_creative_intent(
    project_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
) -> IntentInterviewResponse:
    llm = LLMService(session=session, settings=settings)
    engine = CreativeDirectionEngine(session=session, llm_service=llm)
    intent, _ = await engine._get_or_create_intent(project_id)
    missing = engine._missing_dimensions(intent)
    return IntentInterviewResponse(
        project_id=project_id,
        creative_intent=engine._serialize(intent),
        missing_dimensions=missing,
        is_complete=intent.is_complete,
        next_question=None if intent.is_complete else (f"Share your preference for {missing[0].replace('_', ' ')}." if missing else None),
        quick_options=[],
        target_dimension=missing[0] if missing else None,
    )
