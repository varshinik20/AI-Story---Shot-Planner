"""What-If Exploration Engine: proposes and applies localized alternative shot treatments."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import NotFoundError
from app.db.models.domain import CreativeIntent, ContinuityState, Shot, ShotAlternative
from app.engines.cinematic_reasoning.engine import CinematicReasoningEngine, ShotTreatmentCandidate
from app.engines.production.engine import serialize_shot
from app.services.llm_service import LLMService


class WhatIfOptionItem(BaseModel):
    label: str
    title: str
    framing: str
    camera_angle: str
    camera_movement: str
    duration_seconds: int = Field(..., ge=1, le=30)
    visual_description: str
    emotion: str
    sound: str
    audience_experience_effect: str


class LLMWhatIfPayload(BaseModel):
    alternatives: list[WhatIfOptionItem] = Field(..., min_length=2, max_length=3)


WHAT_IF_SYSTEM_PROMPT = """You are CINEMIND's What-If Exploration Director.
Propose 3 creative alternative visual treatments for the given individual shot without altering the plot or unrelated scenes.
For each option explain clearly how it changes the audience experience (tension, intimacy, scale, emotional resonance).
Return strict JSON matching the schema."""


class WhatIfEngine:
    """Generates and applies localized What-If alternatives on individual shots."""

    def __init__(self, session: AsyncSession, settings: Settings, llm_service: LLMService) -> None:
        self.session = session
        self.settings = settings
        self.llm = llm_service
        self.reasoning = CinematicReasoningEngine(settings=settings, llm_service=llm_service)

    async def generate_alternatives(
        self,
        *,
        shot_uuid: uuid.UUID,
        creative_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        shot = (await self.session.execute(select(Shot).where(Shot.id == shot_uuid))).scalar_one_or_none()
        if shot is None:
            raise NotFoundError("Shot not found.", code="SHOT_NOT_FOUND")

        intent = (
            await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == shot.project_id))
        ).scalar_one_or_none()
        intent_dict = {
            "visual_style": intent.visual_style if intent else None,
            "pacing": intent.pacing if intent else None,
            "lighting": intent.lighting if intent else None,
            "camera_preferences": intent.camera_preferences if intent else None,
        }

        prompt = (
            f"Target Shot {shot.shot_id}:\n"
            f"Current Framing: {shot.framing} | Camera: {shot.camera} | Duration: {shot.duration_seconds}s\n"
            f"Visual Description: {shot.visual_description}\n"
            f"Emotion: {shot.emotion} | Sound: {shot.sound}\n"
            f"Director Intent: {intent_dict}\n"
        )
        if creative_prompt:
            prompt += f"Creator What-If Question: {creative_prompt}\n"
        prompt += "\nGenerate 3 distinct alternative treatments labeled Option A, Option B, Option C."

        payload, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": WHAT_IF_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMWhatIfPayload,
            engine="what_if",
            operation="generate_alternatives",
            project_id=shot.project_id,
            shot_id=shot.shot_id,
            temperature=0.55,
            max_tokens=1500,
        )

        await self.session.execute(delete(ShotAlternative).where(ShotAlternative.shot_uuid == shot.id))
        await self.session.flush()

        rows: list[ShotAlternative] = []
        for idx, opt in enumerate(payload.alternatives, start=1):
            label = opt.label or f"Option {chr(64 + idx)}"
            scored = self.reasoning.score_candidate(
                ShotTreatmentCandidate(
                    label=label,
                    framing=opt.framing,
                    camera_angle=opt.camera_angle,
                    camera_movement=opt.camera_movement,
                    duration_seconds=opt.duration_seconds,
                    lighting_note=intent_dict.get("lighting") or "Scene matched lighting",
                    rationale=opt.audience_experience_effect,
                ),
                emotion=opt.emotion,
                intensity=0.75,
                narrative_role="dramatic_beat",
                creative_intent=intent_dict,
            )
            treatment = {
                "framing": opt.framing,
                "camera": {"angle": opt.camera_angle, "movement": opt.camera_movement},
                "duration_seconds": opt.duration_seconds,
                "visual_description": opt.visual_description,
                "emotion": opt.emotion,
                "sound": opt.sound,
                "reasoning": scored.model_dump(),
            }
            alt = ShotAlternative(
                shot_uuid=shot.id,
                label=label,
                title=opt.title.strip(),
                treatment=treatment,
                audience_experience_effect=opt.audience_experience_effect.strip(),
                is_selected=False,
            )
            self.session.add(alt)
            rows.append(alt)

        await self.session.commit()
        return [
            {
                "id": str(r.id),
                "shot_uuid": str(r.shot_uuid),
                "label": r.label,
                "title": r.title,
                "treatment": r.treatment,
                "audience_experience_effect": r.audience_experience_effect,
                "is_selected": r.is_selected,
            }
            for r in rows
        ]

    async def apply_alternative(
        self,
        *,
        shot_uuid: uuid.UUID,
        alternative_id: uuid.UUID,
    ) -> dict[str, Any]:
        shot = (await self.session.execute(select(Shot).where(Shot.id == shot_uuid))).scalar_one_or_none()
        if shot is None:
            raise NotFoundError("Shot not found.", code="SHOT_NOT_FOUND")

        alternatives = (
            await self.session.execute(select(ShotAlternative).where(ShotAlternative.shot_uuid == shot.id))
        ).scalars().all()
        target = next((a for a in alternatives if a.id == alternative_id), None)
        if target is None:
            raise NotFoundError("Shot alternative not found.", code="ALTERNATIVE_NOT_FOUND")

        for alt in alternatives:
            alt.is_selected = alt.id == alternative_id

        t = target.treatment
        shot.framing = t["framing"]
        shot.camera = t["camera"]
        shot.duration_seconds = int(t["duration_seconds"])
        shot.visual_description = t["visual_description"]
        shot.emotion = t["emotion"]
        shot.sound = t["sound"]
        shot.reasoning = t.get("reasoning")

        self.session.add(
            ContinuityState(
                project_id=shot.project_id,
                scene_uuid=shot.scene_uuid,
                shot_uuid=shot.id,
                state_snapshot={
                    "what_if_applied": target.label,
                    "shot_id": shot.shot_id,
                    "framing": shot.framing,
                    "camera": shot.camera,
                    "emotion": shot.emotion,
                },
            )
        )

        await self.session.commit()
        await self.session.refresh(shot)
        return {
            "applied_alternative_id": str(target.id),
            "shot": serialize_shot(shot),
        }
