from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100
PROJECT_TITLE_MAX_LENGTH = 255
CONVERSATION_TITLE_MAX_LENGTH = 255
MESSAGE_TYPE_DEFAULT = "text"
MESSAGE_TYPE_MAX_LENGTH = 50
