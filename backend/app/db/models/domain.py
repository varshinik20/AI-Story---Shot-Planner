import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Story(Base):
    """Story workspace attached to a project, tracking original, working, and approved text."""

    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    visual_style: Mapped[str | None] = mapped_column(String(255), nullable=True)
    premise: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="typed", server_default="typed")
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    working_content: Mapped[str] = mapped_column(Text, nullable=False)
    approved_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft", index=True)
    structure_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["StoryVersion"]] = relationship(
        back_populates="story", cascade="all, delete-orphan", passive_deletes=True
    )
    suggestions: Mapped[list["StorySuggestion"]] = relationship(
        back_populates="story", cascade="all, delete-orphan", passive_deletes=True
    )


class StoryVersion(Base):
    """Immutable snapshot of original, edited, or approved story versions."""

    __tablename__ = "story_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    story: Mapped["Story"] = relationship(back_populates="versions")


class StorySuggestion(Base):
    """Creator-controlled narrative improvement proposal."""

    __tablename__ = "story_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_passage: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_passage: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    story: Mapped["Story"] = relationship(back_populates="suggestions")


class CreativeIntent(Base):
    """Structured creative direction collected during the adaptive interview."""

    __tablename__ = "creative_intents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    visual_style: Mapped[str | None] = mapped_column(String(255), nullable=True)
    overall_mood: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pacing: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lighting: Mapped[str | None] = mapped_column(String(255), nullable=True)
    camera_preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience_experience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ending_tone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    interview_answers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    pending_questions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Character(Base):
    """Extracted structured character profile from the approved story."""

    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    age_range: Mapped[str | None] = mapped_column(String(80), nullable=True)
    physical_appearance: Mapped[str] = mapped_column(Text, nullable=False)
    clothing: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str] = mapped_column(Text, nullable=False)
    voice_characteristics: Mapped[str] = mapped_column(Text, nullable=False)
    relationships: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    emotional_development: Mapped[str | None] = mapped_column(Text, nullable=True)
    uncertain_details: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Location(Base):
    """Extracted structured location profile."""

    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    lighting_characteristics: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(120), nullable=True)
    visual_elements: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NarrativeEvent(Base):
    """Structured narrative beat extracted for graph modeling and scene sequencing."""

    __tablename__ = "narrative_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    characters: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timeline_position: Mapped[int] = mapped_column(Integer, nullable=False)
    narrative_role: Mapped[str] = mapped_column(String(120), nullable=False)
    narrative_importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    consequence: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion: Mapped[str] = mapped_column(String(120), nullable=False)
    intensity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    continuity_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NarrativeGraph(Base):
    """Persisted NetworkX narrative & emotion graph plus structural diagnostics."""

    __tablename__ = "narrative_graphs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    nodes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    edges: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    story_structure: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Scene(Base):
    """Proposed or approved scene belonging to a project."""

    __tablename__ = "scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[str] = mapped_column(String(32), nullable=False)
    scene_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    shots_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    shots: Mapped[list["Shot"]] = relationship(
        back_populates="scene", cascade="all, delete-orphan", passive_deletes=True, order_by="Shot.shot_order.asc()"
    )


class Shot(Base):
    """Production shot adhering to the Part 11 shot data contract."""

    __tablename__ = "shots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shot_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    shot_order: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    framing: Mapped[str] = mapped_column(String(120), nullable=False)
    camera: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    characters: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    visual_description: Mapped[str] = mapped_column(Text, nullable=False)
    dialogue: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False, default=list)
    emotion: Mapped[str] = mapped_column(String(120), nullable=False)
    sound: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    scene: Mapped["Scene"] = relationship(back_populates="shots")
    alternatives: Mapped[list["ShotAlternative"]] = relationship(
        back_populates="shot", cascade="all, delete-orphan", passive_deletes=True
    )


class ContinuityState(Base):
    """Tracked continuity snapshot after a scene or shot."""

    __tablename__ = "continuity_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_uuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=True
    )
    shot_uuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shots.id", ondelete="CASCADE"), nullable=True
    )
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ShotAlternative(Base):
    """What-If cinematic treatment option for an individual shot."""

    __tablename__ = "shot_alternatives"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shot_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    treatment: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    audience_experience_effect: Mapped[str] = mapped_column(Text, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    shot: Mapped["Shot"] = relationship(back_populates="alternatives")


class ValidationIssue(Base):
    """Continuity, audience experience, or feasibility issue raised for creator review."""

    __tablename__ = "validation_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shot_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreatorApproval(Base):
    """Explicit creator approval gate audit log."""

    __tablename__ = "creator_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gate: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelUsageLog(Base):
    """Telemetry log for every LLM provider call across engines and operations."""

    __tablename__ = "model_usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    engine: Mapped[str] = mapped_column(String(80), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    shot_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
