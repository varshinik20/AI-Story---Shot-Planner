"""Add CINEMIND domain tables and conversation workflow/intake fields.

Revision ID: 0002_cinemind_domain_schema
Revises: 0001_initial_schema
Create Date: 2026-11-27 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_cinemind_domain_schema"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("workflow_stage", sa.String(length=50), server_default="intake", nullable=False),
    )
    op.add_column(
        "conversations",
        sa.Column("intake_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(op.f("ix_conversations_workflow_stage"), "conversations", ["workflow_stage"], unique=False)

    op.create_table(
        "stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("visual_style", sa.String(length=255), nullable=True),
        sa.Column("premise", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), server_default="typed", nullable=False),
        sa.Column("original_content", sa.Text(), nullable=False),
        sa.Column("working_content", sa.Text(), nullable=False),
        sa.Column("approved_content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("structure_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_stories_conversation_id_conversations"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_stories_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stories")),
    )
    op.create_index(op.f("ix_stories_project_id"), "stories", ["project_id"], unique=False)
    op.create_index(op.f("ix_stories_status"), "stories", ["status"], unique=False)

    op.create_table(
        "story_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name=op.f("fk_story_versions_story_id_stories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_story_versions")),
    )
    op.create_index(op.f("ix_story_versions_story_id"), "story_versions", ["story_id"], unique=False)

    op.create_table(
        "story_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=False),
        sa.Column("original_passage", sa.Text(), nullable=False),
        sa.Column("suggested_passage", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], name=op.f("fk_story_suggestions_story_id_stories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_story_suggestions")),
    )
    op.create_index(op.f("ix_story_suggestions_story_id"), "story_suggestions", ["story_id"], unique=False)

    op.create_table(
        "creative_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visual_style", sa.String(length=255), nullable=True),
        sa.Column("overall_mood", sa.String(length=255), nullable=True),
        sa.Column("pacing", sa.String(length=255), nullable=True),
        sa.Column("lighting", sa.String(length=255), nullable=True),
        sa.Column("camera_preferences", sa.Text(), nullable=True),
        sa.Column("audience_experience", sa.String(length=255), nullable=True),
        sa.Column("ending_tone", sa.String(length=255), nullable=True),
        sa.Column("interview_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pending_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_complete", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_creative_intents_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creative_intents")),
        sa.UniqueConstraint("project_id", name=op.f("uq_creative_intents_project_id")),
    )
    op.create_index(op.f("ix_creative_intents_project_id"), "creative_intents", ["project_id"], unique=True)

    op.create_table(
        "characters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("age_range", sa.String(length=80), nullable=True),
        sa.Column("physical_appearance", sa.Text(), nullable=False),
        sa.Column("clothing", sa.Text(), nullable=True),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("voice_characteristics", sa.Text(), nullable=False),
        sa.Column("relationships", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("emotional_development", sa.Text(), nullable=True),
        sa.Column("uncertain_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_characters_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_characters")),
    )
    op.create_index(op.f("ix_characters_project_id"), "characters", ["project_id"], unique=False)

    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=True),
        sa.Column("lighting_characteristics", sa.Text(), nullable=True),
        sa.Column("time_of_day", sa.String(length=120), nullable=True),
        sa.Column("visual_elements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_locations_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
    )
    op.create_index(op.f("ix_locations_project_id"), "locations", ["project_id"], unique=False)

    op.create_table(
        "narrative_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("characters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("timeline_position", sa.Integer(), nullable=False),
        sa.Column("narrative_role", sa.String(length=120), nullable=False),
        sa.Column("narrative_importance", sa.Float(), nullable=False),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("consequence", sa.Text(), nullable=True),
        sa.Column("emotion", sa.String(length=120), nullable=False),
        sa.Column("intensity", sa.Float(), nullable=False),
        sa.Column("continuity_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_narrative_events_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_narrative_events")),
    )
    op.create_index(op.f("ix_narrative_events_project_id"), "narrative_events", ["project_id"], unique=False)

    op.create_table(
        "narrative_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nodes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edges", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("story_structure", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_narrative_graphs_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_narrative_graphs")),
        sa.UniqueConstraint("project_id", name=op.f("uq_narrative_graphs_project_id")),
    )
    op.create_index(op.f("ix_narrative_graphs_project_id"), "narrative_graphs", ["project_id"], unique=True)

    op.create_table(
        "scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_id", sa.String(length=32), nullable=False),
        sa.Column("scene_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("time_of_day", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_approved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("shots_generated", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_scenes_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenes")),
    )
    op.create_index(op.f("ix_scenes_project_id"), "scenes", ["project_id"], unique=False)

    op.create_table(
        "shots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shot_id", sa.String(length=32), nullable=False),
        sa.Column("shot_order", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("framing", sa.String(length=120), nullable=False),
        sa.Column("camera", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("characters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("visual_description", sa.Text(), nullable=False),
        sa.Column("dialogue", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("emotion", sa.String(length=120), nullable=False),
        sa.Column("sound", sa.Text(), nullable=False),
        sa.Column("reasoning", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_shots_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scene_uuid"], ["scenes.id"], name=op.f("fk_shots_scene_uuid_scenes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shots")),
    )
    op.create_index(op.f("ix_shots_project_id"), "shots", ["project_id"], unique=False)
    op.create_index(op.f("ix_shots_scene_uuid"), "shots", ["scene_uuid"], unique=False)
    op.create_index(op.f("ix_shots_shot_id"), "shots", ["shot_id"], unique=False)

    op.create_table(
        "continuity_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shot_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_continuity_states_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scene_uuid"], ["scenes.id"], name=op.f("fk_continuity_states_scene_uuid_scenes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shot_uuid"], ["shots.id"], name=op.f("fk_continuity_states_shot_uuid_shots"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_continuity_states")),
    )
    op.create_index(op.f("ix_continuity_states_project_id"), "continuity_states", ["project_id"], unique=False)

    op.create_table(
        "shot_alternatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shot_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("treatment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audience_experience_effect", sa.Text(), nullable=False),
        sa.Column("is_selected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["shot_uuid"], ["shots.id"], name=op.f("fk_shot_alternatives_shot_uuid_shots"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shot_alternatives")),
    )
    op.create_index(op.f("ix_shot_alternatives_shot_uuid"), "shot_alternatives", ["shot_uuid"], unique=False)

    op.create_table(
        "validation_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("scene_id", sa.String(length=32), nullable=True),
        sa.Column("shot_id", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_validation_issues_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_issues")),
    )
    op.create_index(op.f("ix_validation_issues_project_id"), "validation_issues", ["project_id"], unique=False)

    op.create_table(
        "creator_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gate", sa.String(length=50), nullable=False),
        sa.Column("target_ref", sa.String(length=120), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_creator_approvals_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_creator_approvals")),
    )
    op.create_index(op.f("ix_creator_approvals_gate"), "creator_approvals", ["gate"], unique=False)
    op.create_index(op.f("ix_creator_approvals_project_id"), "creator_approvals", ["project_id"], unique=False)

    op.create_table(
        "model_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("engine", sa.String(length=80), nullable=False),
        sa.Column("operation", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False),
        sa.Column("scene_id", sa.String(length=32), nullable=True),
        sa.Column("shot_id", sa.String(length=32), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_model_usage_logs_conversation_id_conversations"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_model_usage_logs_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_usage_logs")),
    )
    op.create_index(op.f("ix_model_usage_logs_conversation_id"), "model_usage_logs", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_model_usage_logs_project_id"), "model_usage_logs", ["project_id"], unique=False)
    op.create_index(op.f("ix_model_usage_logs_request_id"), "model_usage_logs", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_model_usage_logs_request_id"), table_name="model_usage_logs")
    op.drop_index(op.f("ix_model_usage_logs_project_id"), table_name="model_usage_logs")
    op.drop_index(op.f("ix_model_usage_logs_conversation_id"), table_name="model_usage_logs")
    op.drop_table("model_usage_logs")

    op.drop_index(op.f("ix_creator_approvals_project_id"), table_name="creator_approvals")
    op.drop_index(op.f("ix_creator_approvals_gate"), table_name="creator_approvals")
    op.drop_table("creator_approvals")

    op.drop_index(op.f("ix_validation_issues_project_id"), table_name="validation_issues")
    op.drop_table("validation_issues")

    op.drop_index(op.f("ix_shot_alternatives_shot_uuid"), table_name="shot_alternatives")
    op.drop_table("shot_alternatives")

    op.drop_index(op.f("ix_continuity_states_project_id"), table_name="continuity_states")
    op.drop_table("continuity_states")

    op.drop_index(op.f("ix_shots_shot_id"), table_name="shots")
    op.drop_index(op.f("ix_shots_scene_uuid"), table_name="shots")
    op.drop_index(op.f("ix_shots_project_id"), table_name="shots")
    op.drop_table("shots")

    op.drop_index(op.f("ix_scenes_project_id"), table_name="scenes")
    op.drop_table("scenes")

    op.drop_index(op.f("ix_narrative_graphs_project_id"), table_name="narrative_graphs")
    op.drop_table("narrative_graphs")

    op.drop_index(op.f("ix_narrative_events_project_id"), table_name="narrative_events")
    op.drop_table("narrative_events")

    op.drop_index(op.f("ix_locations_project_id"), table_name="locations")
    op.drop_table("locations")

    op.drop_index(op.f("ix_characters_project_id"), table_name="characters")
    op.drop_table("characters")

    op.drop_index(op.f("ix_creative_intents_project_id"), table_name="creative_intents")
    op.drop_table("creative_intents")

    op.drop_index(op.f("ix_story_suggestions_story_id"), table_name="story_suggestions")
    op.drop_table("story_suggestions")

    op.drop_index(op.f("ix_story_versions_story_id"), table_name="story_versions")
    op.drop_table("story_versions")

    op.drop_index(op.f("ix_stories_status"), table_name="stories")
    op.drop_index(op.f("ix_stories_project_id"), table_name="stories")
    op.drop_table("stories")

    op.drop_index(op.f("ix_conversations_workflow_stage"), table_name="conversations")
    op.drop_column("conversations", "intake_state")
    op.drop_column("conversations", "workflow_stage")
