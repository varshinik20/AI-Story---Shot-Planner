"""Validation endpoints running Continuity, Audience Experience, and Feasibility checks."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.core.exceptions import NotFoundError
from app.db.models.domain import CreativeIntent, NarrativeEvent, Scene, Shot, ValidationIssue
from app.dependencies import DbSession
from app.engines.audience import AudienceFeasibilityEngine
from app.engines.continuity import ContinuityEngine

router = APIRouter(prefix="/validation", tags=["validation"])


class ValidationRunRequest(BaseModel):
    project_id: uuid.UUID


class ValidationIssueOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    category: str
    severity: str
    scene_id: str | None = None
    shot_id: str | None = None
    message: str
    suggested_fix: str | None = None
    resolved: bool


class ValidationReportResponse(BaseModel):
    project_id: uuid.UUID
    issue_count: int
    unresolved_count: int
    issues: list[ValidationIssueOut] = Field(default_factory=list)


@router.post(
    "/run",
    response_model=ValidationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Run continuity, audience experience, and production feasibility validators across the project",
)
async def run_validation(
    payload: ValidationRunRequest,
    session: DbSession,
) -> ValidationReportResponse:
    project_id = payload.project_id
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
    events = list(
        (await session.execute(select(NarrativeEvent).where(NarrativeEvent.project_id == project_id)))
        .scalars()
        .all()
    )
    intent = (
        await session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
    ).scalar_one_or_none()

    shots_by_scene: dict[uuid.UUID, list[Shot]] = {}
    for sh in shots:
        shots_by_scene.setdefault(sh.scene_uuid, []).append(sh)

    continuity_issues = ContinuityEngine(session).validate(
        scenes=scenes,
        shots_by_scene=shots_by_scene,
        events=events,
    )
    audience_issues = AudienceFeasibilityEngine().validate(
        intent=intent,
        scenes=scenes,
        shots_by_scene=shots_by_scene,
    )
    combined = [*continuity_issues, *audience_issues]

    await session.execute(delete(ValidationIssue).where(ValidationIssue.project_id == project_id))
    rows: list[ValidationIssue] = []
    for item in combined:
        row = ValidationIssue(
            project_id=project_id,
            category=item["category"],
            severity=item["severity"],
            scene_id=item.get("scene_id"),
            shot_id=item.get("shot_id"),
            message=item["message"],
            suggested_fix=item.get("suggested_fix"),
            resolved=False,
        )
        session.add(row)
        rows.append(row)

    await session.commit()
    return ValidationReportResponse(
        project_id=project_id,
        issue_count=len(rows),
        unresolved_count=sum(1 for r in rows if not r.resolved),
        issues=[
            ValidationIssueOut(
                id=r.id,
                project_id=r.project_id,
                category=r.category,
                severity=r.severity,
                scene_id=r.scene_id,
                shot_id=r.shot_id,
                message=r.message,
                suggested_fix=r.suggested_fix,
                resolved=r.resolved,
            )
            for r in rows
        ],
    )


@router.post(
    "/{issue_id}/resolve",
    response_model=ValidationIssueOut,
    status_code=status.HTTP_200_OK,
    summary="Mark a validation issue as resolved",
)
async def resolve_validation_issue(
    issue_id: uuid.UUID,
    session: DbSession,
) -> ValidationIssueOut:
    row = (await session.execute(select(ValidationIssue).where(ValidationIssue.id == issue_id))).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Validation issue not found.", code="ISSUE_NOT_FOUND")
    row.resolved = True
    await session.commit()
    return ValidationIssueOut(
        id=row.id,
        project_id=row.project_id,
        category=row.category,
        severity=row.severity,
        scene_id=row.scene_id,
        shot_id=row.shot_id,
        message=row.message,
        suggested_fix=row.suggested_fix,
        resolved=row.resolved,
    )
