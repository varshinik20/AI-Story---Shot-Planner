from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.project_service import ProjectService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_project_service(session: DbSession) -> ProjectService:
    """Provide a request-scoped ProjectService."""
    return ProjectService(session)


def get_conversation_service(session: DbSession) -> ConversationService:
    """Provide a request-scoped ConversationService."""
    return ConversationService(session)


def get_message_service(session: DbSession) -> MessageService:
    """Provide a request-scoped MessageService."""
    return MessageService(session)
