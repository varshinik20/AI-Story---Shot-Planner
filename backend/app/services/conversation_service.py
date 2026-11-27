import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversationNotFoundError, ProjectNotFoundError
from app.db.models.conversation import Conversation
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.conversation import ConversationCreate, ConversationUpdate


class ConversationService:
    """Business operations for project conversations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.conversation_repo = ConversationRepository(session)

    async def create_conversation(
        self,
        project_id: uuid.UUID,
        payload: ConversationCreate,
    ) -> Conversation:
        project = await self.project_repo.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError()

        conversation = await self.conversation_repo.create(
            project_id=project_id,
            title=payload.title,
        )
        await self.session.commit()
        return conversation

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError()
        return conversation

    async def list_project_conversations(
        self,
        project_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Conversation], int]:
        project = await self.project_repo.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError()

        return await self.conversation_repo.list_by_project(
            project_id=project_id,
            limit=limit,
            offset=offset,
        )

    async def update_conversation(
        self,
        conversation_id: uuid.UUID,
        payload: ConversationUpdate,
    ) -> Conversation:
        conversation = await self.get_conversation(conversation_id)
        updates = payload.model_dump(exclude_unset=True)
        if "status" in updates and updates["status"] is not None:
            updates["status"] = updates["status"].value

        if updates:
            conversation = await self.conversation_repo.update(conversation, updates)
            await self.session.commit()
        return conversation

    async def delete_conversation(self, conversation_id: uuid.UUID) -> None:
        conversation = await self.get_conversation(conversation_id)
        await self.conversation_repo.delete(conversation)
        await self.session.commit()
