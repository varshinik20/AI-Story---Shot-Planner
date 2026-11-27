import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversationNotFoundError
from app.db.models.message import Message
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate


class MessageService:
    """Business operations for storing and retrieving conversation messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversation_repo = ConversationRepository(session)
        self.message_repo = MessageRepository(session)

    async def create_message(
        self,
        conversation_id: uuid.UUID,
        payload: MessageCreate,
    ) -> Message:
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()

        message = await self.message_repo.create(
            conversation_id=conversation_id,
            role=payload.role.value,
            content=payload.content,
            message_type=payload.message_type,
            metadata=payload.metadata,
        )
        await self.conversation_repo.touch(conversation)
        await self.session.commit()
        return message

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Message], int]:
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()

        return await self.message_repo.list_by_conversation(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )
