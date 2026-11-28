"""Progressive Production Engine: Scene breakdown, approval, one-scene-at-a-time shot generation."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError
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
)
from app.engines.cinematic_reasoning.engine import CinematicReasoningEngine, ShotTreatmentCandidate
from app.engines.continuity import ContinuityEngine
from app.engines.production.schemas import (
    LLMSceneBreakdownPayload,
    LLMSceneShotsPayload,
    SceneOut,
)
from app.services.llm_service import LLMService

SCENE_SYSTEM_PROMPT = """You are CINEMIND's Production Breakdown Architect.
Group the extracted narrative events into cohesive, filmable scenes (`S01`, `S02`, ...) driven by the NetworkX graph diagnostics (location boundaries, emotional arc peaks, and pacing transition points).
Rules:
1. Every NarrativeEvent `event_id` must appear in at least one scene.
2. Order scenes sequentially (`scene_order` 1..N) with sequential `scene_id` (`S01`, `S02`, ...).
3. Include concise location, time_of_day, and dramatic summary matching the approved story.
Return strict JSON matching the schema."""

SHOT_SYSTEM_PROMPT = """You are CINEMIND's Shot Planner generating the shot list for ONE APPROVED SCENE ONLY.
Follow the Part 11 Shot Data Contract strictly for each shot in this scene:
- shot_id: "{SCENE_PREFIX}_SH01", "{SCENE_PREFIX}_SH02", ... (e.g. "S01_SH01")
- shot_order: 1..N
- duration_seconds: realistic integer (generally 3..6 seconds where suitable)
- framing: cinematic framing (Extreme Wide Shot (EWS), Wide Shot (WS), Medium Shot (MS), Medium Close-Up (MCU), Close-Up (CU), Extreme Close-Up (ECU), Over-the-Shoulder (OTS), Point of View (POV))
- camera: {"angle": "...", "movement": "..."}
- characters: exact names present in this shot (matching extracted Characters)
- location: exact scene/shot location (matching extracted Locations)
- visual_description: concrete visual action respecting the Continuity State from prior scenes
- dialogue: list of {"speaker": "...", "exact_line": "...", "delivery": "..."}.
  CRITICAL DIALOGUE RULE: ONLY include spoken lines that appear VERBATIM in the Approved Story text! If the approved story has NO spoken dialogue for this scene, `dialogue` MUST be an empty list `[]`. NEVER invent spoken dialogue.
- emotion: target emotion
- sound: ambient/SFX/score design

Return strict JSON matching the schema."""


def _normalize_dialogue_against_story(
    dialogue_items: list[dict[str, str]],
    approved_story_text: str,
) -> list[dict[str, str]]:
    """Deterministic guard: strip any invented spoken line not found in the approved story."""
    story_lower = re.sub(r"\s+", " ", approved_story_text).lower()
    verified: list[dict[str, str]] = []
    for item in dialogue_items:
        line = (item.get("exact_line") or "").strip().strip('"\'“”')
        if not line:
            continue
        clean_line = re.sub(r"\s+", " ", line).lower()
        if clean_line in story_lower:
            verified.append(item)
    return verified


def serialize_shot(shot: Shot) -> dict[str, Any]:
    return {
        "id": str(shot.id),
        "project_id": str(shot.project_id),
        "scene_uuid": str(shot.scene_uuid),
        "shot_id": shot.shot_id,
        "shot_order": shot.shot_order,
        "duration_seconds": shot.duration_seconds,
        "framing": shot.framing,
        "camera": shot.camera,
        "characters": shot.characters,
        "location": shot.location,
        "visual_description": shot.visual_description,
        "dialogue": shot.dialogue,
        "emotion": shot.emotion,
        "sound": shot.sound,
        "reasoning": shot.reasoning,
    }


def serialize_scene(scene: Scene, shots: list[Shot]) -> SceneOut:
    return SceneOut(
        id=scene.id,
        project_id=scene.project_id,
        scene_id=scene.scene_id,
        scene_order=scene.scene_order,
        title=scene.title,
        location=scene.location,
        time_of_day=scene.time_of_day,
        summary=scene.summary,
        event_ids=scene.event_ids,
        is_approved=scene.is_approved,
        shots_generated=scene.shots_generated,
        shots=[serialize_shot(s) for s in sorted(shots, key=lambda x: x.shot_order)],
    )


class ProductionEngine:
    """Manages progressive scene breakdown, creator approval, and one-scene-at-a-time shot production."""

    def __init__(self, session: AsyncSession, settings: Settings, llm_service: LLMService) -> None:
        self.session = session
        self.settings = settings
        self.llm = llm_service
        self.continuity = ContinuityEngine(session)
        self.reasoning = CinematicReasoningEngine(settings=settings, llm_service=llm_service)

    async def list_scenes(self, project_id: uuid.UUID) -> list[SceneOut]:
        scenes = (
            await self.session.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_order.asc())
            )
        ).scalars().all()
        shots = (
            await self.session.execute(
                select(Shot).where(Shot.project_id == project_id).order_by(Shot.shot_order.asc())
            )
        ).scalars().all()
        shots_by_scene: dict[uuid.UUID, list[Shot]] = {}
        for sh in shots:
            shots_by_scene.setdefault(sh.scene_uuid, []).append(sh)
        return [serialize_scene(sc, shots_by_scene.get(sc.id, [])) for sc in scenes]

    async def generate_scenes(
        self,
        *,
        project_id: uuid.UUID,
        approve_immediately: bool = False,
    ) -> list[SceneOut]:
        events = (
            await self.session.execute(
                select(NarrativeEvent)
                .where(NarrativeEvent.project_id == project_id)
                .order_by(NarrativeEvent.timeline_position.asc())
            )
        ).scalars().all()
        if not events:
            raise ConflictError(
                "Run narrative analysis first before proposing scenes.",
                code="NARRATIVE_REQUIRED",
            )

        graph = (
            await self.session.execute(select(NarrativeGraph).where(NarrativeGraph.project_id == project_id))
        ).scalar_one_or_none()
        clusters = (graph.diagnostics or {}).get("recommended_scene_clusters", []) if graph else []
        abrupt = (graph.diagnostics or {}).get("abrupt_emotional_transitions", []) if graph else []

        intent = (
            await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
        ).scalar_one_or_none()
        known_locations = list(
            (await self.session.execute(select(Location).where(Location.project_id == project_id))).scalars().all()
        )
        known_loc_names = [loc.name for loc in known_locations]

        events_payload = [
            {
                "event_id": e.event_id,
                "timeline_position": e.timeline_position,
                "description": e.description,
                "location": e.location,
                "emotion": e.emotion,
                "intensity": e.intensity,
                "narrative_role": e.narrative_role,
            }
            for e in events
        ]
        prompt = (
            f"Narrative Events:\n{events_payload}\n\n"
            f"Extracted Locations (use ONLY these canonical names for scene.location): {known_loc_names}\n\n"
            f"NetworkX Recommended Scene Clusters:\n{clusters}\n"
            f"Graph Abrupt Transition Warnings:\n{abrupt}\n"
            f"Creative Intent Pacing/Mood: pacing={intent.pacing if intent else None}, "
            f"mood={intent.overall_mood if intent else None}\n\n"
            "Propose the ordered scenes for creator review."
        )

        payload, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": SCENE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMSceneBreakdownPayload,
            engine="production",
            operation="generate_scenes",
            project_id=project_id,
            temperature=0.35,
            max_tokens=1600,
        )

        await self.session.execute(delete(Scene).where(Scene.project_id == project_id))
        await self.session.flush()

        created: list[Scene] = []
        for idx, item in enumerate(sorted(payload.scenes, key=lambda x: x.scene_order), start=1):
            raw_loc = item.location.strip()
            canonical_loc = next(
                (
                    k
                    for k in known_loc_names
                    if k.lower() == raw_loc.lower() or k.lower() in raw_loc.lower() or raw_loc.lower() in k.lower()
                ),
                raw_loc,
            )
            sc = Scene(
                project_id=project_id,
                scene_id=f"S{idx:02d}",
                scene_order=idx,
                title=item.title.strip(),
                location=canonical_loc,
                time_of_day=item.time_of_day.strip(),
                summary=item.summary.strip(),
                event_ids=item.event_ids,
                is_approved=approve_immediately,
                shots_generated=False,
            )
            self.session.add(sc)
            created.append(sc)

        convs = (
            await self.session.execute(select(Conversation).where(Conversation.project_id == project_id))
        ).scalars().all()
        for conv in convs:
            conv.workflow_stage = "scenes_approved" if approve_immediately else "scene_review"

        await self.session.commit()
        return [serialize_scene(sc, []) for sc in created]

    async def approve_scenes(
        self,
        *,
        project_id: uuid.UUID,
        scene_ids: list[uuid.UUID] | None = None,
        approve_all: bool = False,
    ) -> list[SceneOut]:
        scenes = (
            await self.session.execute(
                select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_order.asc())
            )
        ).scalars().all()
        if not scenes:
            raise NotFoundError("No scenes found for this project.", code="SCENES_NOT_FOUND")

        target_set = set(scene_ids or [])
        approved_codes: list[str] = []
        for sc in scenes:
            if approve_all or sc.id in target_set:
                sc.is_approved = True
                approved_codes.append(sc.scene_id)

        if approved_codes:
            self.session.add(
                CreatorApproval(
                    project_id=project_id,
                    gate="scenes_approved",
                    target_ref=",".join(approved_codes),
                    approved=True,
                )
            )
            convs = (
                await self.session.execute(select(Conversation).where(Conversation.project_id == project_id))
            ).scalars().all()
            for conv in convs:
                conv.workflow_stage = "shot_planning"

        await self.session.commit()
        return await self.list_scenes(project_id)

    async def generate_shots_for_scene(self, *, scene_uuid: uuid.UUID) -> SceneOut:
        scene = (await self.session.execute(select(Scene).where(Scene.id == scene_uuid))).scalar_one_or_none()
        if scene is None:
            raise NotFoundError("Scene not found.", code="SCENE_NOT_FOUND")
        if not scene.is_approved:
            raise ConflictError(
                f"Scene {scene.scene_id} must be approved by the creator before generating shots.",
                code="SCENE_NOT_APPROVED",
            )

        project_id = scene.project_id
        story = (
            await self.session.execute(
                select(Story).where(Story.project_id == project_id).order_by(Story.created_at.desc())
            )
        ).scalars().first()
        approved_story_text = (story.approved_content or story.working_content or story.original_content) if story else ""

        intent = (
            await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
        ).scalar_one_or_none()
        characters = (await self.session.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
        locations = (await self.session.execute(select(Location).where(Location.project_id == project_id))).scalars().all()
        events = (
            await self.session.execute(
                select(NarrativeEvent)
                .where(NarrativeEvent.project_id == project_id)
                .order_by(NarrativeEvent.timeline_position.asc())
            )
        ).scalars().all()

        scene_events = [e for e in events if e.event_id in (scene.event_ids or [])] or events
        continuity_snapshot = await self.continuity.get_latest_snapshot(project_id)
        scene_prefix = f"S{scene.scene_order:02d}"

        intent_dict = {
            "visual_style": intent.visual_style if intent else (story.visual_style if story else None),
            "overall_mood": intent.overall_mood if intent else None,
            "pacing": intent.pacing if intent else None,
            "lighting": intent.lighting if intent else None,
            "camera_preferences": intent.camera_preferences if intent else None,
            "audience_experience": intent.audience_experience if intent else None,
        }

        prompt = (
            f"Scene Prefix: {scene_prefix}\n"
            f"Scene ID: {scene.scene_id} | Title: {scene.title}\n"
            f"Location: {scene.location} ({scene.time_of_day})\n"
            f"Summary: {scene.summary}\n"
            f"Scene Narrative Events: {[{'event_id': e.event_id, 'description': e.description, 'emotion': e.emotion, 'intensity': e.intensity} for e in scene_events]}\n"
            f"Characters: {[{'name': c.name, 'appearance': c.physical_appearance, 'clothing': c.clothing} for c in characters]}\n"
            f"Locations: {[{'name': l.name, 'lighting': l.lighting_characteristics, 'elements': l.visual_elements} for l in locations]}\n"
            f"Prior Continuity State:\n{continuity_snapshot}\n"
            f"Creative Direction:\n{intent_dict}\n\n"
            f"Approved Story Text (ONLY source for verbatim dialogue if any exists):\n{approved_story_text}\n\n"
            f"Generate the ordered shots ONLY for Scene {scene.scene_id} using shot_id format '{scene_prefix}_SH01', '{scene_prefix}_SH02', ..."
        )

        payload, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": SHOT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMSceneShotsPayload,
            engine="production",
            operation="generate_scene_shots",
            project_id=project_id,
            scene_id=scene.scene_id,
            temperature=0.35,
            max_tokens=2200,
        )

        # Replace prior shots ONLY for this specific scene (leave other scenes untouched!)
        await self.session.execute(delete(Shot).where(Shot.scene_uuid == scene.id))
        await self.session.flush()

        prev_shot_dict: dict[str, Any] | None = (
            {
                "framing": continuity_snapshot.get("last_shot_framing"),
                "camera": {"angle": continuity_snapshot.get("last_camera_angle")},
            }
            if continuity_snapshot.get("last_shot_framing")
            else None
        )
        dominant_ev = max(scene_events, key=lambda e: e.intensity) if scene_events else None

        created_shots: list[Shot] = []
        for idx, item in enumerate(sorted(payload.shots, key=lambda x: x.shot_order), start=1):
            raw_dialogue = [d.model_dump() for d in item.dialogue]
            safe_dialogue = _normalize_dialogue_against_story(raw_dialogue, approved_story_text)

            cand = ShotTreatmentCandidate(
                label=f"{scene_prefix}_SH{idx:02d}",
                framing=item.framing,
                camera_angle=item.camera.angle,
                camera_movement=item.camera.movement,
                duration_seconds=item.duration_seconds,
                lighting_note=intent_dict.get("lighting") or scene.time_of_day,
                rationale=item.visual_description,
            )
            scored = self.reasoning.score_candidate(
                cand,
                emotion=item.emotion,
                intensity=dominant_ev.intensity if dominant_ev else 0.6,
                narrative_role=dominant_ev.narrative_role if dominant_ev else "rising_action",
                creative_intent=intent_dict,
                previous_shot=prev_shot_dict,
            )

            shot_row = Shot(
                project_id=project_id,
                scene_uuid=scene.id,
                shot_id=f"{scene_prefix}_SH{idx:02d}",
                shot_order=idx,
                duration_seconds=item.duration_seconds,
                framing=item.framing.strip(),
                camera={"angle": item.camera.angle.strip(), "movement": item.camera.movement.strip()},
                characters=item.characters,
                location=item.location.strip() or scene.location,
                visual_description=item.visual_description.strip(),
                dialogue=safe_dialogue,
                emotion=item.emotion.strip(),
                sound=item.sound.strip(),
                reasoning=scored.model_dump(),
            )
            self.session.add(shot_row)
            created_shots.append(shot_row)
            prev_shot_dict = {"framing": shot_row.framing, "camera": shot_row.camera}

        scene.shots_generated = True
        await self.session.flush()

        await self.continuity.record_scene_state(
            project_id=project_id,
            scene=scene,
            shots=created_shots,
            previous_snapshot=continuity_snapshot,
        )

        await self.session.commit()
        return serialize_scene(scene, created_shots)

    async def update_shot(self, *, shot_uuid: uuid.UUID, updates: dict[str, Any]) -> dict[str, Any]:
        shot = (await self.session.execute(select(Shot).where(Shot.id == shot_uuid))).scalar_one_or_none()
        if shot is None:
            raise NotFoundError("Shot not found.", code="SHOT_NOT_FOUND")

        allowed = {
            "duration_seconds",
            "framing",
            "camera",
            "characters",
            "location",
            "visual_description",
            "dialogue",
            "emotion",
            "sound",
        }
        for key, value in updates.items():
            if key in allowed and value is not None:
                setattr(shot, key, value)

        await self.session.commit()
        await self.session.refresh(shot)
        return serialize_shot(shot)
