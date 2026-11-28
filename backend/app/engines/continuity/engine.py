"""Continuity tracking and validation engine across scenes and shots."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.domain import ContinuityState, NarrativeEvent, Scene, Shot


class ContinuityEngine:
    """Tracks evolving narrative/visual continuity across progressive scene & shot generation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest_snapshot(self, project_id: uuid.UUID) -> dict[str, Any]:
        latest = (
            await self.session.execute(
                select(ContinuityState)
                .where(ContinuityState.project_id == project_id)
                .order_by(ContinuityState.created_at.desc())
            )
        ).scalars().first()
        if latest and isinstance(latest.state_snapshot, dict):
            return dict(latest.state_snapshot)
        return {
            "active_characters": {},
            "current_location": None,
            "current_time_of_day": None,
            "lighting_state": None,
            "last_shot_framing": None,
            "last_camera_angle": None,
            "last_emotion": None,
            "completed_scenes": [],
        }

    async def record_scene_state(
        self,
        *,
        project_id: uuid.UUID,
        scene: Scene,
        shots: list[Shot],
        previous_snapshot: dict[str, Any],
    ) -> ContinuityState:
        snapshot = dict(previous_snapshot)
        active_chars = dict(snapshot.get("active_characters") or {})
        for shot in shots:
            for ch in shot.characters or []:
                active_chars[ch] = {
                    "last_seen_scene": scene.scene_id,
                    "last_seen_shot": shot.shot_id,
                    "location": shot.location,
                    "last_emotion": shot.emotion,
                }

        last_shot = shots[-1] if shots else None
        snapshot.update(
            {
                "active_characters": active_chars,
                "current_location": scene.location,
                "current_time_of_day": scene.time_of_day,
                "last_shot_framing": last_shot.framing if last_shot else snapshot.get("last_shot_framing"),
                "last_camera_angle": (last_shot.camera or {}).get("angle") if last_shot else snapshot.get("last_camera_angle"),
                "last_emotion": last_shot.emotion if last_shot else snapshot.get("last_emotion"),
                "completed_scenes": list({*(snapshot.get("completed_scenes") or []), scene.scene_id}),
            }
        )

        row = ContinuityState(
            project_id=project_id,
            scene_uuid=scene.id,
            shot_uuid=last_shot.id if last_shot else None,
            state_snapshot=snapshot,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    def validate(
        self,
        *,
        scenes: list[Scene],
        shots_by_scene: dict[uuid.UUID, list[Shot]],
        events: list[NarrativeEvent],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        ordered_scenes = sorted(scenes, key=lambda s: s.scene_order)
        if not ordered_scenes:
            issues.append(
                {
                    "category": "continuity",
                    "severity": "error",
                    "scene_id": None,
                    "shot_id": None,
                    "message": "No scenes have been generated for continuity validation.",
                    "suggested_fix": "Generate scenes from the narrative graph before validating.",
                }
            )
            return issues

        # Check all narrative events are covered by scenes
        covered_events = {eid for sc in ordered_scenes for eid in (sc.event_ids or [])}
        for ev in events:
            if ev.event_id not in covered_events:
                issues.append(
                    {
                        "category": "continuity",
                        "severity": "warning",
                        "scene_id": None,
                        "shot_id": None,
                        "message": f"Narrative event {ev.event_id} ('{ev.description[:60]}...') is not assigned to any scene.",
                        "suggested_fix": f"Assign {ev.event_id} to the appropriate scene in the breakdown.",
                    }
                )

        prev_shot: Shot | None = None
        for sc in ordered_scenes:
            sc_shots = sorted(shots_by_scene.get(sc.id, []), key=lambda x: x.shot_order)
            if not sc_shots:
                issues.append(
                    {
                        "category": "continuity",
                        "severity": "warning",
                        "scene_id": sc.scene_id,
                        "shot_id": None,
                        "message": f"Scene {sc.scene_id} ({sc.title}) has no generated shots yet.",
                        "suggested_fix": f"Generate shots for {sc.scene_id} before final approval.",
                    }
                )
                continue

            for idx, shot in enumerate(sc_shots):
                if shot.duration_seconds <= 0:
                    issues.append(
                        {
                            "category": "continuity",
                            "severity": "error",
                            "scene_id": sc.scene_id,
                            "shot_id": shot.shot_id,
                            "message": f"Shot {shot.shot_id} has invalid non-positive duration ({shot.duration_seconds}s).",
                            "suggested_fix": "Set duration_seconds to at least 1 second.",
                        }
                    )

                if prev_shot is not None:
                    same_frame = (prev_shot.framing or "").lower() == (shot.framing or "").lower()
                    same_angle = ((prev_shot.camera or {}).get("angle") or "").lower() == (
                        (shot.camera or {}).get("angle") or ""
                    ).lower()
                    if idx > 0 and same_frame and same_angle:
                        issues.append(
                            {
                                "category": "continuity",
                                "severity": "warning",
                                "scene_id": sc.scene_id,
                                "shot_id": shot.shot_id,
                                "message": (
                                    f"Potential jump cut between {prev_shot.shot_id} and {shot.shot_id}: "
                                    f"consecutive {shot.framing} at {shot.camera.get('angle')}."
                                ),
                                "suggested_fix": "Vary framing or camera angle (or explore What-If alternatives).",
                            }
                        )
                prev_shot = shot

        return issues
