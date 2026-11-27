from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.constants import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from app.dependencies import get_conversation_service
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["Conversations"])

ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]


@router.post(
    "/projects/{project_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Create a conversation inside a project",
)
async def create_conversation(
    project_id: UUID,
    payload: ConversationCreate,
    service: ConversationServiceDep,
) -> ConversationResponse:
    conversation = await service.create_conversation(project_id, payload)
    return ConversationResponse.model_validate(conversation)


@router.get(
    "/projects/{project_id}/conversations",
    response_model=PaginatedResponse[ConversationResponse],
    responses={404: {"model": ErrorResponse}},
    summary="List conversations for a project",
)
async def list_project_conversations(
    project_id: UUID,
    service: ConversationServiceDep,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[ConversationResponse]:
    conversations, total = await service.list_project_conversations(
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse[ConversationResponse](
        items=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get conversation details by ID",
)
async def get_conversation(
    conversation_id: UUID,
    service: ConversationServiceDep,
) -> ConversationResponse:
    conversation = await service.get_conversation(conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Update conversation title or status",
)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    service: ConversationServiceDep,
) -> ConversationResponse:
    conversation = await service.update_conversation(conversation_id, payload)
    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a conversation and its messages",
)
async def delete_conversation(
    conversation_id: UUID,
    service: ConversationServiceDep,
) -> Response:
    await service.delete_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
