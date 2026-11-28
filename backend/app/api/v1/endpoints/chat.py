"""Unified conversational intake and chat orchestration endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.exceptions import ConversationNotFoundError
from app.db.models.domain import Story
from app.dependencies import AppSettings, DbSession
from app.engines.story_intake import IntakeState, StoryIntakeEngine
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.project_repository import ProjectRepository
from app.services.llm_service import LLMService

router = APIRouter(prefix="/chat", tags=["chat"])


class UnifiedChatMessageRequest(BaseModel):
    """Unified message payload for typed text, voice transcripts, or document references."""

    message: str = Field(..., min_length=1, max_length=50000)
    input_source: Literal["text", "voice", "document"] = "text"
    project_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    story_title: str | None = None
    visual_style: str | None = None


class UnifiedChatMessageResponse(BaseModel):
    """Structured response persisted to PostgreSQL."""

    project_id: uuid.UUID
    conversation_id: uuid.UUID
    story_id: uuid.UUID | None = None
    workflow_stage: str
    intent: str
    intake_state: IntakeState
    missing_fields: list[str]
    next_question_field: str | None
    ready_for_story_development: bool
    needs_confirmation: bool
    assistant_message: str
    suggested_titles: list[str] = Field(default_factory=list)
    style_options: list[str] = Field(default_factory=list)
    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID


@router.post(
    "/message",
    response_model=UnifiedChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Unified conversational turn across text and voice into PostgreSQL-backed intake state",
)
async def send_chat_message(
    payload: UnifiedChatMessageRequest,
    session: DbSession,
    settings: AppSettings,
) -> UnifiedChatMessageResponse:
    project_repo = ProjectRepository(session)
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    project = await project_repo.get_by_id(payload.project_id) if payload.project_id else None
    conversation = await conv_repo.get_by_id(payload.conversation_id) if payload.conversation_id else None

    if conversation is not None and project is None:
        project = await project_repo.get_by_id(conversation.project_id)

    if project is None:
        initial_title = (payload.story_title or payload.message[:60]).strip() or "Untitled Story"
        project = await project_repo.create(
            title=initial_title,
            description=payload.visual_style,
        )

    if conversation is None:
        conversation = await conv_repo.create(
            project_id=project.id,
            title=project.title,
        )

    existing_state = IntakeState.model_validate(conversation.intake_state or {})
    if not existing_state.story_title and project.title and project.title != "Untitled Story" and existing_state.title_confirmed:
        existing_state.story_title = project.title
    if not existing_state.visual_style and payload.visual_style:
        existing_state.visual_style = payload.visual_style

    prior_messages, _ = await msg_repo.list_by_conversation(conversation.id, limit=50, offset=0)
    history = [{"role": m.role, "content": m.content} for m in prior_messages if m.role in ("user", "assistant")]

    user_msg = await msg_repo.create(
        conversation_id=conversation.id,
        role="user",
        content=payload.message.strip(),
        message_type=payload.input_source,
        metadata={"input_source": payload.input_source},
    )

    llm_service = LLMService(session=session, settings=settings)
    intake_engine = StoryIntakeEngine(llm_service)
    result = await intake_engine.process_turn(
        project_id=project.id,
        latest_message=payload.message,
        existing_state=existing_state,
        history=history,
        input_source=payload.input_source,
        explicit_title=payload.story_title,
        explicit_visual_style=payload.visual_style,
    )

    # Sync project & conversation fields in PostgreSQL
    new_state = result.intake_state
    if new_state.story_title and new_state.title_confirmed:
        project.title = new_state.story_title
        conversation.title = new_state.story_title
    if new_state.story_context:
        project.description = new_state.story_context[:500]

    conversation.intake_state = new_state.model_dump()
    if result.ready_for_story_development:
        conversation.workflow_stage = "story_ready"
    elif new_state.is_complete():
        conversation.workflow_stage = "intake_confirmation"
    else:
        conversation.workflow_stage = "intake"

    assistant_msg = await msg_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content=result.assistant_message,
        message_type="intake_response",
        metadata={
            "intent": result.intent,
            "missing_fields": result.missing_fields,
            "needs_confirmation": result.needs_confirmation,
            "ready_for_story_development": result.ready_for_story_development,
            "suggested_titles": result.suggested_titles,
            "style_options": result.style_options,
        },
    )

    # Create initial Story row automatically once intake is confirmed (never duplicate per conversation)
    created_story_id: uuid.UUID | None = None
    existing_story = (
        await session.execute(select(Story).where(Story.conversation_id == conversation.id).order_by(Story.created_at.desc()))
    ).scalars().first()
    if existing_story is not None:
        created_story_id = existing_story.id
    elif result.ready_for_story_development and new_state.story_context:
        story = Story(
            project_id=project.id,
            conversation_id=conversation.id,
            title=new_state.story_title or project.title,
            visual_style=new_state.visual_style,
            premise=new_state.story_context,
            source_type="intake_confirmed",
            original_content=new_state.story_context,
            working_content=new_state.story_context,
            structure_json={"dialogue_source": new_state.dialogue_source} if new_state.dialogue_source else None,
            status="draft",
        )
        session.add(story)
        await session.flush()
        created_story_id = story.id

    await session.commit()

    return UnifiedChatMessageResponse(
        project_id=project.id,
        conversation_id=conversation.id,
        story_id=created_story_id,
        workflow_stage=conversation.workflow_stage,
        intent=result.intent,
        intake_state=new_state,
        missing_fields=result.missing_fields,
        next_question_field=result.next_question_field,
        ready_for_story_development=result.ready_for_story_development,
        needs_confirmation=result.needs_confirmation,
        assistant_message=result.assistant_message,
        suggested_titles=result.suggested_titles,
        style_options=result.style_options,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
    )


@router.get(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Restore persisted conversation messages and story intake state",
)
async def get_conversation_intake_state(
    conversation_id: uuid.UUID,
    session: DbSession,
) -> dict:
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)
    conversation = await conv_repo.get_by_id(conversation_id)
    if conversation is None:
        raise ConversationNotFoundError()
    messages, _ = await msg_repo.list_by_conversation(conversation.id, limit=200, offset=0)
    story = (
        await session.execute(select(Story).where(Story.conversation_id == conversation.id).order_by(Story.created_at.desc()))
    ).scalars().first()
    return {
        "project_id": str(conversation.project_id),
        "conversation_id": str(conversation.id),
        "story_id": str(story.id) if story else None,
        "title": conversation.title,
        "workflow_stage": conversation.workflow_stage,
        "intake_state": IntakeState.model_validate(conversation.intake_state or {}).model_dump(),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "input_source": (m.message_metadata or {}).get("input_source", m.message_type),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
