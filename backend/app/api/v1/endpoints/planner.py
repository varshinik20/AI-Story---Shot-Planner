"""Planner approval gate, hydrated workspace read, and gated ReportLab PDF export."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.exceptions import ConflictError, ProjectNotFoundError
from app.db.models.conversation import Conversation
from app.db.models.domain import (
    Character,
    CreativeIntent,
    CreatorApproval,
    Location,
    NarrativeEvent,
    NarrativeGraph,
    Scene,
    Shot,
    Story,
    ValidationIssue,
)
from app.db.models.project import Project
from app.dependencies import DbSession
from app.engines.production import serialize_scene
from app.services.pdf import PDFValidationError, PlannerPDFService, validate_planner_for_export

router = APIRouter(prefix="/planner", tags=["planner"])


class PlannerApproveRequest(BaseModel):
    project_id: uuid.UUID
    notes: str | None = None
    allow_partial: bool = False


class PlannerApproveResponse(BaseModel):
    project_id: uuid.UUID
    approved: bool
    approved_at: datetime
    scene_count: int
    shot_count: int
    export_url: str


@router.post(
    "/approve",
    response_model=PlannerApproveResponse,
    status_code=status.HTTP_200_OK,
    summary="Explicit creator approval gate unlocking final PDF shot planner export",
)
async def approve_planner(
    payload: PlannerApproveRequest,
    session: DbSession,
) -> PlannerApproveResponse:
    project = (
        await session.execute(select(Project).where(Project.id == payload.project_id))
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError()

    scenes = list(
        (
            await session.execute(
                select(Scene)
                .where(Scene.project_id == payload.project_id)
                .order_by(Scene.scene_order.asc())
            )
        )
        .scalars()
        .all()
    )
    if not scenes:
        raise ConflictError("Cannot approve shot planner before scenes exist.", code="SCENES_MISSING")

    shots = list(
        (await session.execute(select(Shot).where(Shot.project_id == payload.project_id)))
        .scalars()
        .all()
    )
    if not shots:
        raise ConflictError("Cannot approve shot planner before generating shots.", code="SHOTS_MISSING")

    if not payload.allow_partial:
        missing_scenes = [sc.scene_id for sc in scenes if not sc.shots_generated]
        if missing_scenes:
            raise ConflictError(
                f"Generate shots for all approved scenes before final approval (missing: {', '.join(missing_scenes)}).",
                code="INCOMPLETE_SCENE_SHOTS",
            )

    approval = CreatorApproval(
        project_id=payload.project_id,
        gate="final_shot_plan",
        target_ref=f"{len(scenes)} scenes / {len(shots)} shots",
        approved=True,
        notes=payload.notes,
    )
    session.add(approval)
    project.status = "completed"

    convs = (
        await session.execute(select(Conversation).where(Conversation.project_id == payload.project_id))
    ).scalars().all()
    for conv in convs:
        conv.workflow_stage = "approved_for_export"

    await session.commit()
    await session.refresh(approval)

    return PlannerApproveResponse(
        project_id=payload.project_id,
        approved=True,
        approved_at=approval.approved_at,
        scene_count=len(scenes),
        shot_count=len(shots),
        export_url=f"/api/v1/planner/export/{payload.project_id}",
    )


@router.get(
    "/export/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Export creator-approved Shot Planner as a production PDF via ReportLab",
)
async def export_planner_pdf(
    project_id: uuid.UUID,
    session: DbSession,
) -> Response:
    project = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError()

    approval = (
        await session.execute(
            select(CreatorApproval)
            .where(
                CreatorApproval.project_id == project_id,
                CreatorApproval.gate == "final_shot_plan",
                CreatorApproval.approved.is_(True),
            )
            .order_by(CreatorApproval.approved_at.desc())
        )
    ).scalars().first()
    if approval is None:
        raise ConflictError(
            "Creator approval of the final shot plan is required before exporting the PDF.",
            code="PLANNER_NOT_APPROVED",
        )

    story = (
        await session.execute(
            select(Story).where(Story.project_id == project_id).order_by(Story.created_at.desc())
        )
    ).scalars().first()
    intent = (
        await session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
    ).scalar_one_or_none()
    characters = list(
        (await session.execute(select(Character).where(Character.project_id == project_id)))
        .scalars()
        .all()
    )
    locations = list(
        (await session.execute(select(Location).where(Location.project_id == project_id)))
        .scalars()
        .all()
    )
    scenes = list(
        (
            await session.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_order.asc())
            )
        )
        .scalars()
        .all()
    )
    shots = list(
        (
            await session.execute(
                select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_order.asc())
            )
        )
        .scalars()
        .all()
    )
    shots_by_scene: dict[uuid.UUID, list[Shot]] = {}
    for sh in shots:
        shots_by_scene.setdefault(sh.scene_uuid, []).append(sh)

    pdf_bytes = PlannerPDFService().build_planner_pdf(
        project=project,
        story=story,
        intent=intent,
        characters=characters,
        locations=locations,
        scenes=scenes,
        shots_by_scene=shots_by_scene,
        approved_at=approval.approved_at,
        validate=True,
    )

    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "-", project.title).strip("-") or "Project"
    filename = f"Shot-Planner_{safe_title}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.get(
    "/validate-pdf/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Validate planner completeness and accuracy before PDF export",
)
async def validate_planner_pdf_endpoint(
    project_id: uuid.UUID,
    session: DbSession,
) -> dict[str, Any]:
    project = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError()

    story = (
        await session.execute(
            select(Story).where(Story.project_id == project_id).order_by(Story.created_at.desc())
        )
    ).scalars().first()
    intent = (
        await session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
    ).scalar_one_or_none()
    characters = list(
        (await session.execute(select(Character).where(Character.project_id == project_id)))
        .scalars()
        .all()
    )
    locations = list(
        (await session.execute(select(Location).where(Location.project_id == project_id)))
        .scalars()
        .all()
    )
    scenes = list(
        (
            await session.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_order.asc())
            )
        )
        .scalars()
        .all()
    )
    shots = list(
        (
            await session.execute(
                select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_order.asc())
            )
        )
        .scalars()
        .all()
    )
    shots_by_scene: dict[uuid.UUID, list[Shot]] = {}
    for sh in shots:
        shots_by_scene.setdefault(sh.scene_uuid, []).append(sh)

    try:
        summary = validate_planner_for_export(
            project=project,
            story=story,
            intent=intent,
            characters=characters,
            locations=locations,
            scenes=scenes,
            shots_by_scene=shots_by_scene,
        )
        return {
            "valid": True,
            "issues": [],
            "scene_count": summary.scene_count,
            "shot_count": summary.shot_count,
            "dialogue_lines_count": summary.dialogue_lines_count,
            "total_runtime_seconds": summary.total_runtime_seconds,
            "character_count": summary.character_count,
            "location_count": summary.location_count,
        }
    except PDFValidationError as exc:
        return {
            "valid": False,
            "issues": exc.issues,
        }


@router.get(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Fetch complete hydrated project workspace state for frontend persistence",
)
async def get_planner_workspace(
    project_id: uuid.UUID,
    session: DbSession,
) -> dict[str, Any]:
    project = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError()

    story = (
        await session.execute(select(Story).where(Story.project_id == project_id).order_by(Story.created_at.desc()))
    ).scalars().first()
    intent = (
        await session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
    ).scalar_one_or_none()
    graph = (
        await session.execute(select(NarrativeGraph).where(NarrativeGraph.project_id == project_id))
    ).scalar_one_or_none()
    characters = list(
        (await session.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
    )
    locations = list(
        (await session.execute(select(Location).where(Location.project_id == project_id))).scalars().all()
    )
    events = list(
        (await session.execute(select(NarrativeEvent).where(NarrativeEvent.project_id == project_id)))
        .scalars()
        .all()
    )
    scenes = list(
        (await session.execute(select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_order.asc())))
        .scalars()
        .all()
    )
    shots = list(
        (await session.execute(select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_order.asc())))
        .scalars()
        .all()
    )
    issues = list(
        (await session.execute(select(ValidationIssue).where(ValidationIssue.project_id == project_id)))
        .scalars()
        .all()
    )
    approvals = list(
        (await session.execute(select(CreatorApproval).where(CreatorApproval.project_id == project_id)))
        .scalars()
        .all()
    )

    shots_by_scene: dict[uuid.UUID, list[Shot]] = {}
    for sh in shots:
        shots_by_scene.setdefault(sh.scene_uuid, []).append(sh)

    final_approved = any(a.gate == "final_shot_plan" and a.approved for a in approvals)
    return {
        "project": {
            "id": str(project.id),
            "title": project.title,
            "description": project.description,
            "status": project.status,
        },
        "story": (
            {
                "id": str(story.id),
                "title": story.title,
                "visual_style": story.visual_style,
                "working_content": story.working_content,
                "approved_content": story.approved_content,
                "status": story.status,
            }
            if story
            else None
        ),
        "creative_intent": (
            {
                "visual_style": intent.visual_style,
                "overall_mood": intent.overall_mood,
                "pacing": intent.pacing,
                "lighting": intent.lighting,
                "camera_preferences": intent.camera_preferences,
                "audience_experience": intent.audience_experience,
                "ending_tone": intent.ending_tone,
                "is_complete": intent.is_complete,
            }
            if intent
            else None
        ),
        "characters": [
            {
                "id": str(c.id),
                "character_code": c.character_code,
                "name": c.name,
                "role": c.role,
                "physical_appearance": c.physical_appearance,
                "clothing": c.clothing,
                "personality": c.personality,
                "voice_characteristics": c.voice_characteristics,
                "emotional_development": c.emotional_development,
                "uncertain_details": c.uncertain_details or [],
            }
            for c in characters
        ],
        "locations": [
            {
                "id": str(l.id),
                "location_code": l.location_code,
                "name": l.name,
                "description": l.description,
                "lighting_characteristics": l.lighting_characteristics,
                "time_of_day": l.time_of_day,
                "visual_elements": l.visual_elements or [],
            }
            for l in locations
        ],
        "events_count": len(events),
        "narrative_diagnostics": graph.diagnostics if graph else None,
        "scenes": [serialize_scene(sc, shots_by_scene.get(sc.id, [])).model_dump() for sc in scenes],
        "validation_issues": [
            {
                "id": str(i.id),
                "category": i.category,
                "severity": i.severity,
                "scene_id": i.scene_id,
                "shot_id": i.shot_id,
                "message": i.message,
                "suggested_fix": i.suggested_fix,
                "resolved": i.resolved,
            }
            for i in issues
        ],
        "final_approved": final_approved,
        "export_url": f"/api/v1/planner/export/{project_id}" if final_approved else None,
    }
