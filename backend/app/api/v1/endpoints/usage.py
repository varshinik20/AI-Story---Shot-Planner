"""Token & execution cost usage telemetry endpoint."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.exceptions import ProjectNotFoundError
from app.db.models.domain import ModelUsageLog
from app.db.models.project import Project
from app.dependencies import DbSession

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Aggregate real LLM token, latency, and cost telemetry per project",
)
async def get_project_usage(
    project_id: uuid.UUID,
    session: DbSession,
) -> dict[str, Any]:
    project = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError()

    logs = list(
        (
            await session.execute(
                select(ModelUsageLog)
                .where(ModelUsageLog.project_id == project_id)
                .order_by(ModelUsageLog.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    total_input = sum(l.input_tokens or 0 for l in logs)
    total_output = sum(l.output_tokens or 0 for l in logs)
    costs = [l.estimated_cost_usd for l in logs if l.estimated_cost_usd is not None]
    total_cost = round(sum(costs), 6) if costs else None

    by_engine: dict[str, dict[str, Any]] = {}
    for l in logs:
        bucket = by_engine.setdefault(
            l.engine,
            {
                "calls": 0,
                "successful_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "estimated_cost_usd": None,
                "execution_time_ms": 0,
            },
        )
        bucket["calls"] += 1
        if l.success:
            bucket["successful_calls"] += 1
        bucket["input_tokens"] += l.input_tokens or 0
        bucket["output_tokens"] += l.output_tokens or 0
        bucket["execution_time_ms"] += l.execution_time_ms
        if l.estimated_cost_usd is not None:
            bucket["estimated_cost_usd"] = round((bucket["estimated_cost_usd"] or 0.0) + l.estimated_cost_usd, 6)

    return {
        "project_id": str(project_id),
        "total_calls": len(logs),
        "successful_calls": sum(1 for l in logs if l.success),
        "failed_calls": sum(1 for l in logs if not l.success),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_estimated_cost_usd": total_cost,
        "total_execution_time_ms": sum(l.execution_time_ms for l in logs),
        "by_engine": by_engine,
        "logs": [
            {
                "id": str(l.id),
                "request_id": l.request_id,
                "engine": l.engine,
                "operation": l.operation,
                "model": l.model,
                "input_tokens": l.input_tokens,
                "output_tokens": l.output_tokens,
                "estimated_cost_usd": l.estimated_cost_usd,
                "execution_time_ms": l.execution_time_ms,
                "scene_id": l.scene_id,
                "shot_id": l.shot_id,
                "success": l.success,
                "error_message": l.error_message,
            }
            for l in logs
        ],
    }
