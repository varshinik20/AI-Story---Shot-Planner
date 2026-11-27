import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import Conversation


class ConversationRepository:
    """Data access methods for Conversation records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        project_id: uuid.UUID,
        title: str | None = None,
    ) -> Conversation:
        conversation = Conversation(project_id=project_id, title=title)
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Conversation], int]:
        count_stmt = (
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.project_id == project_id)
        )
        total = int((await self.session.execute(count_stmt)).scalar_one())

        stmt = (
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def update(
        self,
        conversation: Conversation,
        updates: dict[str, object],
    ) -> Conversation:
        for field, value in updates.items():
            setattr(conversation, field, value)
        conversation.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def touch(self, conversation: Conversation) -> None:
        conversation.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def delete(self, conversation: Conversation) -> None:
        await self.session.delete(conversation)
        await self.session.flush()
