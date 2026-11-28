"""Story document upload & collaborative story development endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, UploadFile, status
from pydantic import BaseModel, Field

from app.core.exceptions import ProjectNotFoundError
from app.db.models.domain import Story
from app.dependencies import AppSettings, DbSession
from app.engines.story_development import StoryDevelopmentEngine
from app.engines.story_development.schemas import (
    ApproveStoryRequest,
    DevelopStoryRequest,
    StoryDetailResponse,
    SuggestionDecisionRequest,
)
from app.engines.story_intake import IntakeState, StoryIntakeEngine
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.project_repository import ProjectRepository
from app.services.document_service import DocumentService
from app.services.llm_service import LLMService

router = APIRouter(prefix="/stories", tags=["stories"])


class StoryUploadResponse(BaseModel):
    """Response returned after extracting and persisting an uploaded story document."""

    project_id: uuid.UUID
    conversation_id: uuid.UUID
    story_id: uuid.UUID
    filename: str
    file_type: str
    word_count: int
    page_count: int | None
    extracted_text: str
    workflow_stage: str
    intake_state: IntakeState
    missing_fields: list[str]
    needs_confirmation: bool
    ready_for_story_development: bool
    assistant_message: str
    style_options: list[str] = Field(default_factory=list)


@router.post(
    "/upload",
    response_model=StoryUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a TXT, PDF, or DOCX story file into the unified intake pipeline",
)
async def upload_story_document(
    session: DbSession,
    settings: AppSettings,
    file: UploadFile = File(...),
    project_id: uuid.UUID | None = Form(default=None),
    conversation_id: uuid.UUID | None = Form(default=None),
    story_title: str | None = Form(default=None),
    visual_style: str | None = Form(default=None),
) -> StoryUploadResponse:
    raw_bytes = await file.read()
    doc_service = DocumentService(max_bytes=settings.UPLOAD_MAX_BYTES)
    extracted = doc_service.extract_text(filename=file.filename or "upload.txt", content_bytes=raw_bytes)

    project_repo = ProjectRepository(session)
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    conversation = await conv_repo.get_by_id(conversation_id) if conversation_id else None
    project = await project_repo.get_by_id(project_id) if project_id else None
    if project_id and project is None:
        raise ProjectNotFoundError()
    if conversation is not None and project is None:
        project = await project_repo.get_by_id(conversation.project_id)

    if project is None:
        project = await project_repo.create(
            title=(story_title or extracted.filename.rsplit(".", 1)[0]).strip() or "Uploaded Story",
            description=extracted.extracted_text[:500],
        )
    else:
        project.description = extracted.extracted_text[:500]
        if story_title and story_title.strip():
            project.title = story_title.strip()

    if conversation is None:
        conversation = await conv_repo.create(project_id=project.id, title=project.title)

    existing_state = IntakeState.model_validate(conversation.intake_state or {})
    prior_messages, _ = await msg_repo.list_by_conversation(conversation.id, limit=50, offset=0)
    history = [
        {"role": m.role, "content": m.content}
        for m in prior_messages
        if m.role in ("user", "assistant")
    ]

    await msg_repo.create(
        conversation_id=conversation.id,
        role="user",
        content=f'[Uploaded {extracted.filename} — {extracted.word_count} words]\n\n{extracted.extracted_text[:4000]}',
        message_type="document",
        metadata={
            "input_source": "document",
            "filename": extracted.filename,
            "file_type": extracted.file_type,
            "word_count": extracted.word_count,
            "page_count": extracted.page_count,
            "sha256": extracted.sha256,
        },
    )

    llm_service = LLMService(session=session, settings=settings)
    intake_engine = StoryIntakeEngine(llm_service)
    result = await intake_engine.process_turn(
        project_id=project.id,
        latest_message=extracted.extracted_text,
        existing_state=existing_state,
        history=history,
        input_source="document",
        uploaded_filename=extracted.filename,
        explicit_title=story_title,
        explicit_visual_style=visual_style,
    )

    # Preserve full extracted text unconditionally in intake_state.story_context and Story
    result.intake_state.story_context = extracted.extracted_text
    conversation.intake_state = result.intake_state.model_dump()
    if result.ready_for_story_development:
        conversation.workflow_stage = "story_ready"
    elif result.intake_state.is_complete():
        conversation.workflow_stage = "intake_confirmation"
    else:
        conversation.workflow_stage = "intake"

    story = Story(
        project_id=project.id,
        conversation_id=conversation.id,
        title=result.intake_state.story_title or (story_title.strip() if story_title else extracted.filename.rsplit(".", 1)[0]),
        visual_style=result.intake_state.visual_style,
        premise=extracted.extracted_text[:1000],
        source_type="uploaded",
        original_content=extracted.extracted_text,
        working_content=extracted.extracted_text,
        status="draft",
    )
    session.add(story)
    await session.flush()

    await msg_repo.create(
        conversation_id=conversation.id,
        role="assistant",
        content=result.assistant_message,
        message_type="intake_response",
        metadata={
            "intent": result.intent,
            "missing_fields": result.missing_fields,
            "needs_confirmation": result.needs_confirmation,
            "story_id": str(story.id),
            "style_options": result.style_options,
        },
    )
    await session.commit()

    return StoryUploadResponse(
        project_id=project.id,
        conversation_id=conversation.id,
        story_id=story.id,
        filename=extracted.filename,
        file_type=extracted.file_type,
        word_count=extracted.word_count,
        page_count=extracted.page_count,
        extracted_text=extracted.extracted_text,
        workflow_stage=conversation.workflow_stage,
        intake_state=result.intake_state,
        missing_fields=result.missing_fields,
        needs_confirmation=result.needs_confirmation,
        ready_for_story_development=result.ready_for_story_development,
        assistant_message=result.assistant_message,
        style_options=result.style_options,
    )


@router.post(
    "/develop",
    response_model=StoryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Collaboratively develop story draft and generate creator-controlled suggestions",
)
async def develop_story(
    payload: DevelopStoryRequest,
    session: DbSession,
    settings: AppSettings,
) -> StoryDetailResponse:
    llm = LLMService(session=session, settings=settings)
    engine = StoryDevelopmentEngine(session=session, llm_service=llm)
    return await engine.develop_story(
        story_id=payload.story_id,
        project_id=payload.project_id,
        instruction=payload.instruction,
        preserve_original_text=payload.preserve_original_text,
    )


@router.post(
    "/suggestions/{suggestion_id}/decision",
    response_model=StoryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept or reject a specific story improvement suggestion",
)
async def decide_story_suggestion(
    suggestion_id: uuid.UUID,
    payload: SuggestionDecisionRequest,
    session: DbSession,
    settings: AppSettings,
) -> StoryDetailResponse:
    llm = LLMService(session=session, settings=settings)
    engine = StoryDevelopmentEngine(session=session, llm_service=llm)
    return await engine.decide_suggestion(
        suggestion_id=suggestion_id,
        decision=payload.decision,
        edited_text=payload.edited_text,
    )


@router.post(
    "/approve",
    response_model=StoryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve final working story text and lock immutable approved snapshot",
)
async def approve_story(
    payload: ApproveStoryRequest,
    session: DbSession,
    settings: AppSettings,
) -> StoryDetailResponse:
    llm = LLMService(session=session, settings=settings)
    engine = StoryDevelopmentEngine(session=session, llm_service=llm)
    return await engine.approve_story(
        story_id=payload.story_id,
        edited_content=payload.edited_content,
    )


@router.get(
    "/{story_id}",
    response_model=StoryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch full story state including versions and suggestions",
)
async def get_story_detail(
    story_id: uuid.UUID,
    session: DbSession,
    settings: AppSettings,
) -> StoryDetailResponse:
    llm = LLMService(session=session, settings=settings)
    engine = StoryDevelopmentEngine(session=session, llm_service=llm)
    return await engine.get_story_detail(story_id)
