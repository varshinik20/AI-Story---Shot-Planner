"""Automated one-line idea -> Complete Story, CINEMIND Analysis, Scene/Shot Planner & PDF orchestrator."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
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
    StoryVersion,
    ValidationIssue,
)
from app.db.models.project import Project
from app.engines.audience import AudienceFeasibilityEngine
from app.engines.continuity import ContinuityEngine
from app.engines.narrative_emotion import NarrativeEmotionEngine
from app.engines.production import ProductionEngine
from app.engines.production.schemas import SceneOut
from app.engines.story_intake import IntakeState
from app.engines.story_intelligence import StoryIntelligenceEngine
from app.services.llm_service import LLMService
from app.services.pdf.planner_pdf_validator import (
    PDFValidationError,
    PlannerValidationSummary,
    validate_planner_for_export,
)

logger = logging.getLogger("cinemind.orchestrator.story_to_planner")

_NON_STORY_GREETINGS = re.compile(
    r"^\s*(hi+|hello+|hey+|good\s+(morning|afternoon|evening)|help|menu|start|what\s+can\s+you\s+do|who\s+are\s+you|how\s+does\s+this\s+work)\s*[!.?]*\s*$",
    re.IGNORECASE,
)


def is_uninterpretable_input(text: str) -> bool:
    """Return True only when user input has zero narrative seed (e.g. 'hi', 'help', empty symbols)."""
    cleaned = text.strip()
    if not cleaned:
        return True
    if _NON_STORY_GREETINGS.match(cleaned):
        return True
    alpha_chars = sum(1 for ch in cleaned if ch.isalpha())
    return alpha_chars < 3


class LLMOneLineConceptPayload(BaseModel):
    """Structured creative analysis and complete story generated from any input seed."""

    title: str = Field(..., min_length=2, max_length=140)
    logline: str = Field(..., min_length=8, max_length=400)
    genre: str = Field(..., min_length=2, max_length=120)
    central_theme: str = Field(..., min_length=4, max_length=280)
    synopsis: str = Field(..., min_length=15)
    developed_story: str = Field(..., min_length=80)
    beginning_summary: str = Field(..., min_length=8)
    middle_summary: str = Field(..., min_length=8)
    ending_summary: str = Field(..., min_length=8)
    dialogue_present: bool = True
    visual_style: str = Field(..., min_length=3, max_length=160)
    colour_palette: str = Field(..., min_length=4, max_length=240)
    overall_atmosphere: str = Field(..., min_length=4, max_length=240)
    overall_mood: str = Field(..., min_length=4, max_length=160)
    pacing: str = Field(..., min_length=4, max_length=160)
    lighting: str = Field(..., min_length=4, max_length=220)
    camera_preferences: str = Field(..., min_length=4, max_length=220)
    character_treatment: str = Field(..., min_length=4, max_length=240)
    audience_experience: str = Field(..., min_length=4, max_length=220)
    ending_tone: str = Field(..., min_length=4, max_length=160)
    desired_ending_experience: str = Field(..., min_length=4, max_length=240)


class LLMFollowupEditPayload(BaseModel):
    """Follow-up creator change request on an existing generated story/planner."""

    updated_title: str | None = None
    updated_genre: str | None = None
    updated_visual_style: str | None = None
    updated_story_text: str | None = None
    updated_logline: str | None = None
    updated_central_theme: str | None = None
    rebuild_scenes_and_shots: bool = False
    assistant_reply: str = Field(..., min_length=4)


CONCEPT_EXPANSION_SYSTEM_PROMPT = """You are CINEMIND's Lead Screenwriter, Narrative Architect, and Creative Director.
The creator will give you ANY creative seed — a one-line idea (e.g. "The girl chased her dream."), a theme, a conflict, a voice note, or an uploaded story draft.

Your mission is to turn that seed IMMEDIATELY into a complete, emotionally compelling, production-ready film story and creative direction profile WITHOUT asking the creator for missing fields.

REQUIREMENTS:
1. Title:
   - If the creator explicitly named a title, preserve it.
   - Otherwise craft an original, evocative, story-specific title (avoid generic clichés like "Untitled Story" or "A New Beginning").
2. Concept & Genre:
   - Identify the best-fit genre (or hybrid genre) and central theme while preserving the creator's exact premise and intention.
   - Do NOT add bloated subplots or unnecessary extra characters that dilute a focused idea.
3. Complete Developed Story (`developed_story`):
   - Write a vivid, cinematic narrative with distinct beginning, middle, turning point, climax, and coherent resolution.
   - Keep character names, ages/appearances, motivations, and locations consistent throughout.
   - DIALOGUE IS REQUIRED: this story becomes an animated film with voiced characters, so write natural spoken dialogue throughout — not only at the climax. Every story beat where two or more characters share the moment (or a character reacts aloud) MUST contain 1–3 short spoken lines. Aim for roughly 12–25 spoken lines across the whole story, spread across the beginning, middle, climax and resolution.
   - Format every spoken line in double quotes with an explicit named speaker in the same sentence (e.g. `Maya whispered, "I am not turning back."`). Keep lines short (under ~15 words) and in character; one line per quote.
   - The ONLY exceptions: a genuinely wordless/silent concept explicitly requested by the creator, or a single-character beat with nobody to speak to (a brief inner exclamation is still welcome).
   - If uploaded/existing source prose is marked `preserve_story_text=true`, keep its plot, character names, and dialogue lines intact while lightly structuring it if needed.
4. Creative Direction:
   - Infer cohesive visual_style, colour_palette, overall_atmosphere, overall_mood, pacing, lighting, camera_preferences, character_treatment, audience_experience, ending_tone, and desired_ending_experience suited to the story.

Return strict JSON matching the schema."""

FOLLOWUP_EDIT_SYSTEM_PROMPT = """You are CINEMIND's Creative Partner helping a filmmaker refine their generated Story and Shot Planner.
Read the current project state (title, genre, visual style, story text) and the creator's latest instruction.
- Apply ONLY the changes requested (such as renaming the title, shifting genre, changing visual style, revising the ending, or editing plot beats).
- Preserve all untouched story details carefully.
- Set `rebuild_scenes_and_shots: true` whenever story prose, dialogue, characters, locations, or plot changed so scenes and shots stay consistent; keep `false` for title/metadata-only changes.
Return strict JSON matching the schema."""


@dataclass(slots=True)
class OrchestratedPlannerResult:
    """Summary returned by the full automated pipeline."""

    project: Project
    conversation: Conversation
    story: Story
    scene_count: int
    shot_count: int
    dialogue_lines_count: int
    total_runtime_seconds: int
    character_count: int
    location_count: int
    assistant_message: str
    intake_state: IntakeState


class StoryToPlannerOrchestrator:
    """Coordinates all CINEMIND engines into a single end-to-end story-to-planner workflow."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        llm_service: LLMService,
    ) -> None:
        self.session = session
        self.settings = settings
        self.llm = llm_service

    async def _run_downstream_cinemind_pipeline(
        self,
        *,
        project: Project,
        story: Story,
    ) -> tuple[list[Character], list[Location], list[SceneOut], PlannerValidationSummary]:
        """Execute Intelligence -> Narrative Graph -> Scenes -> Shots -> Continuity/Feasibility -> Approval."""
        intel_engine = StoryIntelligenceEngine(session=self.session, llm_service=self.llm)
        characters, locations, events, story_structure = await intel_engine.extract_entities(
            project_id=project.id,
            story_id=story.id,
        )

        # Ensure every speaker in quoted dialogue is grounded cleanly & graph runs cleanly
        graph_engine = NarrativeEmotionEngine(session=self.session)
        await graph_engine.build_and_analyze(
            project_id=project.id,
            characters=characters,
            locations=locations,
            events=events,
            story_structure=story_structure,
        )

        production = ProductionEngine(
            session=self.session,
            settings=self.settings,
            llm_service=self.llm,
        )
        # Approve scenes immediately so per-scene shot generation executes continuously
        await production.generate_scenes(
            project_id=project.id,
            approve_immediately=True,
        )

        db_scenes = list(
            (
                await self.session.execute(
                    select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_order.asc())
                )
            )
            .scalars()
            .all()
        )

        scene_outs: list[SceneOut] = []
        for sc in db_scenes:
            sc_out = await production.generate_shots_for_scene(scene_uuid=sc.id)
            scene_outs.append(sc_out)

        # Reload canonical rows after all scene shots commit
        characters = list(
            (await self.session.execute(select(Character).where(Character.project_id == project.id))).scalars().all()
        )
        locations = list(
            (await self.session.execute(select(Location).where(Location.project_id == project.id))).scalars().all()
        )
        intent = (
            await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project.id))
        ).scalar_one_or_none()
        scenes = list(
            (
                await self.session.execute(
                    select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_order.asc())
                )
            )
            .scalars()
            .all()
        )
        shots = list(
            (
                await self.session.execute(
                    select(Shot).where(Shot.project_id == project.id).order_by(Shot.shot_order.asc())
                )
            )
            .scalars()
            .all()
        )
        shots_by_scene: dict[uuid.UUID, list[Shot]] = {}
        for sh in shots:
            shots_by_scene.setdefault(sh.scene_uuid, []).append(sh)

        # Deterministic continuity & production feasibility validation
        continuity_issues = ContinuityEngine(self.session).validate(
            scenes=scenes,
            shots_by_scene=shots_by_scene,
            events=events,
        )
        feasibility_issues = AudienceFeasibilityEngine().validate(
            intent=intent,
            scenes=scenes,
            shots_by_scene=shots_by_scene,  # type: ignore[arg-type]
        )

        await self.session.execute(delete(ValidationIssue).where(ValidationIssue.project_id == project.id))
        for item in [*continuity_issues, *feasibility_issues]:
            self.session.add(
                ValidationIssue(
                    project_id=project.id,
                    category=str(item["category"]),
                    severity=str(item["severity"]),
                    scene_id=item.get("scene_id"),
                    shot_id=item.get("shot_id"),
                    message=str(item["message"]),
                    suggested_fix=item.get("suggested_fix"),
                    resolved=False,
                )
            )

        summary = self._validate_and_stabilize_for_pdf(
            project=project,
            story=story,
            intent=intent,
            characters=characters,
            locations=locations,
            scenes=scenes,
            shots_by_scene=shots_by_scene,
        )

        # Record final approval so creator can immediately export OR further customize & re-export
        await self.session.execute(
            delete(CreatorApproval).where(
                CreatorApproval.project_id == project.id,
                CreatorApproval.gate == "final_shot_plan",
            )
        )
        self.session.add(
            CreatorApproval(
                project_id=project.id,
                gate="final_shot_plan",
                target_ref=f"{summary.scene_count} scenes / {summary.shot_count} shots",
                approved=True,
                notes="Automatically generated and validated by CINEMIND pipeline.",
            )
        )
        project.status = "completed"
        await self.session.flush()
        return characters, locations, scene_outs, summary

    def _validate_and_stabilize_for_pdf(
        self,
        *,
        project: Project,
        story: Story,
        intent: CreativeIntent | None,
        characters: list[Character],
        locations: list[Location],
        scenes: list[Scene],
        shots_by_scene: dict[uuid.UUID, list[Shot]],
    ) -> PlannerValidationSummary:
        """Validate all planner tables for PDF export and deterministically fix minor normalization drift."""
        known_loc_names = [loc.name for loc in locations if loc.name]
        known_char_names = [ch.name for ch in characters if ch.name]
        fallback_loc = known_loc_names[0] if known_loc_names else "Main Setting"

        if not scenes:
            # Should not happen unless malformed LLM output; validated right below.
            pass

        seen_ids: set[str] = set()
        for sc in sorted(scenes, key=lambda s: s.scene_order):
            if known_loc_names and sc.location not in known_loc_names:
                matched_sc_loc = next(
                    (k for k in known_loc_names if k.lower() in (sc.location or "").lower() or (sc.location or "").lower() in k.lower()),
                    fallback_loc,
                )
                sc.location = matched_sc_loc

            sc_shots = sorted(shots_by_scene.get(sc.id, []), key=lambda x: x.shot_order)
            for idx, sh in enumerate(sc_shots, start=1):
                expected_id = f"S{sc.scene_order:02d}_SH{idx:02d}"
                if not sh.shot_id or sh.shot_id in seen_ids:
                    sh.shot_id = expected_id
                seen_ids.add(sh.shot_id)

                if sh.duration_seconds <= 0:
                    sh.duration_seconds = 4

                if known_loc_names:
                    matched_loc = next(
                        (
                            k
                            for k in known_loc_names
                            if k.lower() == (sh.location or "").lower()
                            or k.lower() in (sh.location or "").lower()
                            or (sh.location or "").lower() in k.lower()
                        ),
                        sc.location if sc.location in known_loc_names else fallback_loc,
                    )
                    sh.location = matched_loc

                if known_char_names and sh.characters:
                    cleaned_chars: list[str] = []
                    for ref in sh.characters:
                        match_c = next(
                            (
                                k
                                for k in known_char_names
                                if k.lower() == ref.lower() or ref.lower() in k.lower() or k.lower() in ref.lower()
                            ),
                            None,
                        )
                        if match_c and match_c not in cleaned_chars:
                            cleaned_chars.append(match_c)
                    sh.characters = cleaned_chars

        return validate_planner_for_export(
            project=project,
            story=story,
            intent=intent,
            characters=characters,
            locations=locations,
            scenes=scenes,
            shots_by_scene=shots_by_scene,
        )

    async def generate_from_idea(
        self,
        *,
        project: Project,
        conversation: Conversation,
        user_input: str,
        input_source: str = "text",
        explicit_title: str | None = None,
        explicit_visual_style: str | None = None,
        preserve_story_text: str | None = None,
    ) -> OrchestratedPlannerResult:
        """Transform any creative seed into a saved Story, Intent, Graph, Scenes, Shots, and exportable PDF."""
        source_seed = (preserve_story_text or user_input).strip()
        concept_prompt = (
            f"Creator Input ({input_source}):\n{source_seed}\n\n"
            f"Explicit Title Override: {explicit_title or 'None (infer a vivid title)'}\n"
            f"Explicit Visual Style Override: {explicit_visual_style or 'None (infer best-fit cinematic style)'}\n"
            f"preserve_story_text: {'true' if preserve_story_text else 'false'}\n"
        )

        concept, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": CONCEPT_EXPANSION_SYSTEM_PROMPT},
                {"role": "user", "content": concept_prompt},
            ],
            schema_model=LLMOneLineConceptPayload,
            engine="story_development",
            operation="one_line_concept_expansion",
            project_id=project.id,
            temperature=0.55,
            max_tokens=3200,
        )

        final_title = (explicit_title or concept.title).strip() or "Untitled Film"
        final_style = (explicit_visual_style or concept.visual_style).strip() or "Realistic Cinematic Film"
        final_story_text = (preserve_story_text or concept.developed_story).strip()

        project.title = final_title
        project.description = concept.logline.strip()[:500]
        conversation.title = final_title

        intake_state = IntakeState(
            story_title=final_title,
            title_confirmed=True,
            visual_style=final_style,
            story_context=final_story_text,
            confirmed_by_creator=True,
            awaiting_confirmation=False,
            input_sources_seen=[input_source],  # type: ignore[list-item]
            current_stage="approved_for_export",
            confirmation_status="confirmed",
            generation_status="completed",
        )
        conversation.intake_state = intake_state.model_dump()
        conversation.workflow_stage = "approved_for_export"

        structure_meta: dict[str, Any] = {
            "logline": concept.logline.strip(),
            "genre": concept.genre.strip(),
            "central_theme": concept.central_theme.strip(),
            "synopsis": concept.synopsis.strip(),
            "beginning": concept.beginning_summary.strip(),
            "middle": concept.middle_summary.strip(),
            "ending": concept.ending_summary.strip(),
            "colour_palette": concept.colour_palette.strip(),
            "dialogue_present": concept.dialogue_present,
        }

        existing_story = (
            await self.session.execute(
                select(Story).where(Story.conversation_id == conversation.id).order_by(Story.created_at.desc())
            )
        ).scalars().first()
        if existing_story is None:
            story = Story(
                project_id=project.id,
                conversation_id=conversation.id,
                title=final_title,
                visual_style=final_style,
                premise=concept.logline.strip(),
                source_type="uploaded" if preserve_story_text else "one_line_idea",
                original_content=source_seed,
                working_content=final_story_text,
                approved_content=final_story_text,
                status="approved",
                structure_json=structure_meta,
            )
            self.session.add(story)
            await self.session.flush()
        else:
            story = existing_story
            story.title = final_title
            story.visual_style = final_style
            story.premise = concept.logline.strip()
            story.working_content = final_story_text
            story.approved_content = final_story_text
            story.status = "approved"
            story.structure_json = structure_meta

        # Record clean StoryVersion snapshots
        await self.session.execute(delete(StoryVersion).where(StoryVersion.story_id == story.id))
        self.session.add_all(
            [
                StoryVersion(
                    story_id=story.id,
                    version_number=1,
                    label="original",
                    content=source_seed,
                    is_approved=False,
                ),
                StoryVersion(
                    story_id=story.id,
                    version_number=2,
                    label="approved",
                    content=final_story_text,
                    is_approved=True,
                ),
            ]
        )

        # Persist complete CreativeIntent matching PlannerPDFService & CINEMIND schemas
        await self.session.execute(delete(CreativeIntent).where(CreativeIntent.project_id == project.id))
        intent = CreativeIntent(
            project_id=project.id,
            visual_style=final_style,
            overall_mood=concept.overall_mood.strip(),
            pacing=concept.pacing.strip(),
            lighting=concept.lighting.strip(),
            camera_preferences=concept.camera_preferences.strip(),
            audience_experience=concept.audience_experience.strip(),
            ending_tone=concept.ending_tone.strip(),
            interview_answers={
                "production_format": "16:9 · 24 FPS",
                "genre": concept.genre.strip(),
                "colour_palette": concept.colour_palette.strip(),
                "overall_atmosphere": concept.overall_atmosphere.strip(),
                "character_treatment": concept.character_treatment.strip(),
                "intended_emotional_impact": concept.audience_experience.strip(),
                "lighting_and_color": f"{concept.lighting.strip()} ({concept.colour_palette.strip()})",
                "desired_ending_experience": concept.desired_ending_experience.strip(),
                "central_theme": concept.central_theme.strip(),
            },
            pending_questions=[],
            is_complete=True,
        )
        self.session.add(intent)
        await self.session.flush()

        characters, locations, _scenes, summary = await self._run_downstream_cinemind_pipeline(
            project=project,
            story=story,
        )

        char_names = ", ".join(c.name for c in characters[:5])
        loc_names = ", ".join(loc.name for loc in locations[:5])
        assistant_msg = (
            f"I've analysed your idea and developed it into **{final_title}** ({concept.genre.strip()}), "
            f"complete with story expansion, character and location profiles, cinematic scene breakdown, and a ready-to-export shot planner.\n\n"
            f"- **Logline:** {concept.logline.strip()}\n"
            f"- **Visual Direction:** {final_style} · {concept.colour_palette.strip()}\n"
            f"- **Characters ({summary.character_count}):** {char_names}\n"
            f"- **Locations ({summary.location_count}):** {loc_names}\n"
            f"- **Production Plan:** {summary.scene_count} scenes · {summary.shot_count} shots · "
            f"{summary.dialogue_lines_count} dialogue lines · {summary.total_runtime_seconds}s runtime (16:9 · 24 FPS)\n\n"
            "Review or edit the story, individual scenes, or shots in the workspace below, or click **Download Production PDF** anytime."
        )
        intake_state.last_assistant_question = assistant_msg
        conversation.intake_state = intake_state.model_dump()
        conversation.workflow_stage = "approved_for_export"
        await self.session.commit()

        return OrchestratedPlannerResult(
            project=project,
            conversation=conversation,
            story=story,
            scene_count=summary.scene_count,
            shot_count=summary.shot_count,
            dialogue_lines_count=summary.dialogue_lines_count,
            total_runtime_seconds=summary.total_runtime_seconds,
            character_count=summary.character_count,
            location_count=summary.location_count,
            assistant_message=assistant_msg,
            intake_state=intake_state,
        )

    async def regenerate_full_planner(
        self,
        *,
        project: Project,
        story: Story,
    ) -> PlannerValidationSummary:
        """Rebuild Intelligence, NetworkX Graph, Scenes, Shots, Validation & Approval from edited/updated Story."""
        intent = (
            await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project.id))
        ).scalar_one_or_none()
        if intent is not None and story.visual_style:
            intent.visual_style = story.visual_style
        _, _, _, summary = await self._run_downstream_cinemind_pipeline(
            project=project,
            story=story,
        )
        convs = (
            await self.session.execute(select(Conversation).where(Conversation.project_id == project.id))
        ).scalars().all()
        for conv in convs:
            conv.workflow_stage = "approved_for_export"
        await self.session.commit()
        return summary

    async def apply_creator_followup(
        self,
        *,
        project: Project,
        conversation: Conversation,
        story: Story,
        instruction: str,
    ) -> tuple[str, IntakeState]:
        """Apply conversational edit/regeneration requests against an already generated Story & Shot Planner."""
        structure = dict(story.structure_json or {})
        prompt = (
            f"Current Title: {story.title}\n"
            f"Current Genre: {structure.get('genre', 'Drama')}\n"
            f"Current Visual Style: {story.visual_style or 'Realistic Cinematic Film'}\n"
            f"Current Story:\n{story.approved_content or story.working_content}\n\n"
            f"Creator Instruction: {instruction}\n"
        )
        edit_res, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": FOLLOWUP_EDIT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMFollowupEditPayload,
            engine="story_development",
            operation="followup_creator_edit",
            project_id=project.id,
            temperature=0.4,
            max_tokens=2600,
        )

        if edit_res.updated_title and edit_res.updated_title.strip():
            new_title = edit_res.updated_title.strip()
            project.title = new_title
            conversation.title = new_title
            story.title = new_title

        if edit_res.updated_visual_style and edit_res.updated_visual_style.strip():
            new_style = edit_res.updated_visual_style.strip()
            story.visual_style = new_style
            intent = (
                await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project.id))
            ).scalar_one_or_none()
            if intent is not None:
                intent.visual_style = new_style

        if edit_res.updated_genre and edit_res.updated_genre.strip():
            structure["genre"] = edit_res.updated_genre.strip()
        if edit_res.updated_logline and edit_res.updated_logline.strip():
            structure["logline"] = edit_res.updated_logline.strip()
            story.premise = edit_res.updated_logline.strip()
            project.description = edit_res.updated_logline.strip()[:500]
        if edit_res.updated_central_theme and edit_res.updated_central_theme.strip():
            structure["central_theme"] = edit_res.updated_central_theme.strip()
        story.structure_json = structure

        if edit_res.updated_story_text and edit_res.updated_story_text.strip():
            new_story_text = edit_res.updated_story_text.strip()
            story.working_content = new_story_text
            story.approved_content = new_story_text

        if edit_res.rebuild_scenes_and_shots or (edit_res.updated_story_text and edit_res.updated_story_text.strip()):
            summary = await self.regenerate_full_planner(project=project, story=story)
            reply = (
                f"{edit_res.assistant_reply.strip()} "
                f"(Updated planner: {summary.scene_count} scenes, {summary.shot_count} shots, {summary.total_runtime_seconds}s runtime.)"
            )
        else:
            await self.session.commit()
            reply = edit_res.assistant_reply.strip()

        state = IntakeState.model_validate(conversation.intake_state or {})
        state.story_title = story.title
        state.visual_style = story.visual_style
        state.story_context = story.approved_content or story.working_content
        state.confirmed_by_creator = True
        state.current_stage = "approved_for_export"
        state.last_assistant_question = reply
        conversation.intake_state = state.model_dump()
        await self.session.commit()
        return reply, state
