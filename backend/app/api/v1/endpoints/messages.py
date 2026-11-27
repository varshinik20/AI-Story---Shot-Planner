from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.constants import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from app.dependencies import get_message_service
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.services.message_service import MessageService

router = APIRouter(tags=["Messages"])

MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Store a message in a conversation",
)
async def create_message(
    conversation_id: UUID,
    payload: MessageCreate,
    service: MessageServiceDep,
) -> MessageResponse:
    message = await service.create_message(conversation_id, payload)
    return MessageResponse.model_validate(message)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=PaginatedResponse[MessageResponse],
    responses={404: {"model": ErrorResponse}},
    summary="Retrieve conversation messages in chronological order",
)
async def list_messages(
    conversation_id: UUID,
    service: MessageServiceDep,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[MessageResponse]:
    messages, total = await service.list_messages(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse[MessageResponse](
        items=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        limit=limit,
        offset=offset,
    )
