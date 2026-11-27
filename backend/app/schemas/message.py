from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import (
    MESSAGE_TYPE_DEFAULT,
    MESSAGE_TYPE_MAX_LENGTH,
    MessageRole,
)


class MessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)
    message_type: str = Field(
        default=MESSAGE_TYPE_DEFAULT,
        min_length=1,
        max_length=MESSAGE_TYPE_MAX_LENGTH,
    )
    metadata: dict[str, Any] | None = Field(default=None)

    @field_validator("content")
    @classmethod
    def validate_content_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Message content cannot be empty or whitespace.")
        return value

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message_type cannot be empty.")
        return cleaned


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    message_type: str
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias="message_metadata",
    )
    created_at: datetime
