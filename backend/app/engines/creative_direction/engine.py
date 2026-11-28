"""Creative Direction Engine: adaptive filmmaking intent interview avoiding redundant questions."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectNotFoundError
from app.db.models.conversation import Conversation
from app.db.models.domain import CreativeIntent, Story
from app.db.models.project import Project
from app.engines.creative_direction.schemas import (
    CreativeIntentData,
    IntentInterviewResponse,
    LLMIntentInterviewPayload,
)
from app.services.llm_service import LLMService

REQUIRED_DIMENSIONS = [
    "visual_style",
    "overall_mood",
    "pacing",
    "lighting",
    "camera_preferences",
    "audience_experience",
    "ending_tone",
]

DIMENSION_DEFAULT_OPTIONS: dict[str, list[str]] = {
    "overall_mood": ["Tense & Suspenseful", "Melancholic & Emotional", "Warm & Hopeful", "Eerie & Atmospheric"],
    "pacing": ["Slow-burn atmospheric", "Urgent & kinetic", "Measured & contemplative", "Escalating build-up"],
    "lighting": ["Naturalistic overcast dusk", "High-contrast chiaroscuro", "Golden warm twilight", "Cold desaturated mist"],
    "camera_preferences": ["Intimate handheld tracking", "Smooth cinematic Steadicam", "Static composed wide frames", "Dynamic crane & close-ups"],
    "audience_experience": ["General / Family", "Young Adult", "Mature Thriller / Drama", "Festival Short Film"],
    "ending_tone": ["Haunting cliffhanger", "Emotional bittersweet release", "Hopeful resolution", "Shocking reversal"],
}

INTERVIEW_SYSTEM_PROMPT = """You are CINEMIND's Creative Direction Partner interviewing a filmmaker after story approval to build a complete Creative Intent profile before narrative graph analysis and shot planning.

Collect these 7 dimensions (only fill what is clearly stated or unambiguously established — NEVER overwrite existing confirmed fields unless the user explicitly asks to change one):
1. visual_style
2. overall_mood
3. pacing
4. lighting
5. camera_preferences
6. audience_experience (e.g. Children, Family, Young Adult, Adult Thriller/Drama)
7. ending_tone

Rules:
- NEVER repeat a question for any dimension already populated.
- If multiple dimensions remain missing, ask ONE natural, director-friendly question targeting the most impactful missing dimension (`target_dimension`) and offer 3-4 concise `quick_options`.
- If all dimensions are filled, confirm readiness concisely in `next_question` and return empty `quick_options`.
Return strict JSON."""


class CreativeDirectionEngine:
    """Adaptive interview engine persisting CreativeIntent to PostgreSQL."""

    def __init__(self, session: AsyncSession, llm_service: LLMService) -> None:
        self.session = session
        self.llm = llm_service

    def _missing_dimensions(self, intent: CreativeIntent) -> list[str]:
        missing: list[str] = []
        for dim in REQUIRED_DIMENSIONS:
            val = getattr(intent, dim, None)
            if not val or not str(val).strip():
                missing.append(dim)
        return missing

    def _serialize(self, intent: CreativeIntent) -> CreativeIntentData:
        return CreativeIntentData(
            id=intent.id,
            project_id=intent.project_id,
            visual_style=intent.visual_style,
            overall_mood=intent.overall_mood,
            pacing=intent.pacing,
            lighting=intent.lighting,
            camera_preferences=intent.camera_preferences,
            audience_experience=intent.audience_experience,
            ending_tone=intent.ending_tone,
            interview_answers=intent.interview_answers or {},
            pending_questions=intent.pending_questions or [],
            is_complete=intent.is_complete,
        )

    async def _get_or_create_intent(self, project_id: uuid.UUID) -> tuple[CreativeIntent, Story | None]:
        project = (await self.session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
        if project is None:
            raise ProjectNotFoundError()

        story = (
            await self.session.execute(
                select(Story).where(Story.project_id == project_id).order_by(Story.created_at.desc())
            )
        ).scalars().first()

        intent = (
            await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
        ).scalar_one_or_none()
        if intent is None:
            intent = CreativeIntent(
                project_id=project_id,
                visual_style=story.visual_style if story else None,
                interview_answers={},
                pending_questions=list(REQUIRED_DIMENSIONS),
                is_complete=False,
            )
            self.session.add(intent)
            await self.session.flush()
        elif not intent.visual_style and story and story.visual_style:
            intent.visual_style = story.visual_style

        return intent, story

    async def _sync_stage_if_complete(self, project_id: uuid.UUID, intent: CreativeIntent) -> None:
        if intent.is_complete:
            convs = (
                await self.session.execute(select(Conversation).where(Conversation.project_id == project_id))
            ).scalars().all()
            for conv in convs:
                if conv.workflow_stage in ("intake", "intake_confirmation", "story_ready", "story_development", "intent_interview"):
                    conv.workflow_stage = "narrative_ready"

    async def run_interview(
        self,
        *,
        project_id: uuid.UUID,
        story_id: uuid.UUID | None = None,
    ) -> IntentInterviewResponse:
        intent, story = await self._get_or_create_intent(project_id)
        if story_id is not None:
            explicit_story = (
                await self.session.execute(select(Story).where(Story.id == story_id))
            ).scalar_one_or_none()
            if explicit_story is not None:
                story = explicit_story

        missing_before = self._missing_dimensions(intent)
        if not missing_before:
            intent.is_complete = True
            intent.pending_questions = []
            await self._sync_stage_if_complete(project_id, intent)
            await self.session.commit()
            return IntentInterviewResponse(
                project_id=project_id,
                creative_intent=self._serialize(intent),
                missing_dimensions=[],
                is_complete=True,
                next_question="Your creative direction profile is complete and ready for narrative analysis.",
                quick_options=[],
                target_dimension=None,
            )

        story_text = (story.approved_content or story.working_content) if story else ""
        prompt = (
            f"Approved Story:\n{story_text}\n\n"
            f"Already captured CreativeIntent:\n{self._serialize(intent).model_dump()}\n\n"
            f"Missing dimensions: {missing_before}\n"
            "Infer only what is undeniably clear from the story's tone/style if applicable, otherwise leave missing, "
            "and ask ONE focused director question for the highest-priority missing dimension."
        )

        payload, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMIntentInterviewPayload,
            engine="creative_direction",
            operation="interview_prompt",
            project_id=project_id,
            temperature=0.35,
            max_tokens=700,
        )

        self._apply_llm_fields(intent, payload, overwrite=False)
        missing_after = self._missing_dimensions(intent)
        intent.pending_questions = missing_after
        intent.is_complete = len(missing_after) == 0
        await self._sync_stage_if_complete(project_id, intent)
        await self.session.commit()

        target_dim = payload.target_dimension if payload.target_dimension in missing_after else (missing_after[0] if missing_after else None)
        options = payload.quick_options or (DIMENSION_DEFAULT_OPTIONS.get(target_dim, []) if target_dim else [])

        return IntentInterviewResponse(
            project_id=project_id,
            creative_intent=self._serialize(intent),
            missing_dimensions=missing_after,
            is_complete=intent.is_complete,
            next_question=payload.next_question if missing_after else "Your creative direction is ready for narrative analysis.",
            quick_options=options if missing_after else [],
            target_dimension=target_dim,
        )

    async def submit_answer(
        self,
        *,
        project_id: uuid.UUID,
        answer: str | None = None,
        updates: dict[str, str] | None = None,
        confirm: bool = False,
    ) -> IntentInterviewResponse:
        intent, story = await self._get_or_create_intent(project_id)

        answers_log = dict(intent.interview_answers or {})
        if updates:
            for key, value in updates.items():
                if key in REQUIRED_DIMENSIONS and isinstance(value, str) and value.strip():
                    setattr(intent, key, value.strip())
                    answers_log[key] = value.strip()

        next_question: str | None = None
        quick_options: list[str] = []
        target_dim: str | None = None

        if answer and answer.strip():
            story_text = (story.approved_content or story.working_content) if story else ""
            prompt = (
                f"Story Context:\n{story_text[:2000]}\n\n"
                f"Current CreativeIntent:\n{self._serialize(intent).model_dump()}\n\n"
                f"Creator's latest response:\n{answer.strip()}\n\n"
                "Extract any dimensions answered (visual_style, overall_mood, pacing, lighting, "
                "camera_preferences, audience_experience, ending_tone) and generate next_question for the next missing dimension."
            )
            payload, _ = await self.llm.generate_json(
                messages=[
                    {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                schema_model=LLMIntentInterviewPayload,
                engine="creative_direction",
                operation="interview_answer",
                project_id=project_id,
                temperature=0.3,
                max_tokens=700,
            )
            self._apply_llm_fields(intent, payload, overwrite=True)
            answers_log[f"turn_{len(answers_log) + 1}"] = answer.strip()
            next_question = payload.next_question
            quick_options = payload.quick_options
            target_dim = payload.target_dimension

        intent.interview_answers = answers_log
        missing = self._missing_dimensions(intent)
        intent.pending_questions = missing
        if confirm and len(missing) <= 2:
            intent.is_complete = True
        else:
            intent.is_complete = len(missing) == 0

        await self._sync_stage_if_complete(project_id, intent)
        await self.session.commit()

        if intent.is_complete:
            return IntentInterviewResponse(
                project_id=project_id,
                creative_intent=self._serialize(intent),
                missing_dimensions=missing,
                is_complete=True,
                next_question="Creative direction locked! Ready to analyze narrative beats and emotional graph.",
                quick_options=[],
                target_dimension=None,
            )

        next_dim = target_dim if target_dim in missing else missing[0]
        if not next_question:
            next_question = f"Could you share your preference for {next_dim.replace('_', ' ')}?"
        if not quick_options:
            quick_options = DIMENSION_DEFAULT_OPTIONS.get(next_dim, [])

        return IntentInterviewResponse(
            project_id=project_id,
            creative_intent=self._serialize(intent),
            missing_dimensions=missing,
            is_complete=False,
            next_question=next_question,
            quick_options=quick_options,
            target_dimension=next_dim,
        )

    def _apply_llm_fields(
        self,
        intent: CreativeIntent,
        payload: LLMIntentInterviewPayload,
        *,
        overwrite: bool,
    ) -> None:
        for dim in REQUIRED_DIMENSIONS:
            incoming = getattr(payload, dim, None)
            existing = getattr(intent, dim, None)
            if incoming and str(incoming).strip():
                if overwrite or not existing:
                    setattr(intent, dim, str(incoming).strip())
