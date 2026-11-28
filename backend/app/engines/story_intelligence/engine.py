"""Story Intelligence Engine: extracts structured characters, locations, events, and story structure."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.domain import Character, CreativeIntent, Location, NarrativeEvent, Story
from app.engines.story_intelligence.schemas import LLMStoryIntelligencePayload
from app.services.llm_service import LLMService

INTELLIGENCE_SYSTEM_PROMPT = """You are CINEMIND's Story Intelligence Engine.
Analyze the creator's approved story and creative direction into grounded production entities.

STRICT ACCURACY RULES:
1. Extract ONLY characters, locations, actions, and events supported by the story text.
2. NEVER invent unsupported biographical facts (age, hidden backstory, props, or clothing) as certainty — if a detail like age_range or clothing is unstated in the text, describe only what is grounded and list what was unstated inside `uncertain_details`.
3. Break the narrative into chronological `events` (E001, E002, ...) capturing:
   - exact action description,
   - characters involved,
   - location name,
   - timeline_position (1..N),
   - narrative_role (`opening_setup`, `inciting_incident`, `rising_action`, `climax`, `falling_action`, `resolution`),
   - narrative_importance (0.0 to 1.0),
   - cause & consequence strings linking events cleanly,
   - primary emotion & emotional intensity (0.0 to 1.0),
   - continuity_info (character state, props, wardrobe condition, spatial position).
4. Set `story_structure.dialogue_present=true` ONLY if spoken dialogue appears in the story text.
Return strict JSON matching the schema."""


class StoryIntelligenceEngine:
    """Extracts and persists grounded Characters, Locations, and NarrativeEvents."""

    def __init__(self, session: AsyncSession, llm_service: LLMService) -> None:
        self.session = session
        self.llm = llm_service

    async def extract_entities(
        self,
        *,
        project_id: uuid.UUID,
        story_id: uuid.UUID | None = None,
    ) -> tuple[list[Character], list[Location], list[NarrativeEvent], dict]:
        stmt = select(Story).where(Story.project_id == project_id)
        if story_id is not None:
            stmt = select(Story).where(Story.id == story_id, Story.project_id == project_id)
        else:
            stmt = stmt.order_by(Story.created_at.desc())

        story = (await self.session.execute(stmt)).scalars().first()
        if story is None:
            raise NotFoundError("Story not found for intelligence extraction.", code="STORY_NOT_FOUND")

        story_text = (story.approved_content or story.working_content or story.original_content).strip()
        intent = (
            await self.session.execute(select(CreativeIntent).where(CreativeIntent.project_id == project_id))
        ).scalar_one_or_none()

        intent_summary = {
            "visual_style": (intent.visual_style if intent else story.visual_style),
            "overall_mood": intent.overall_mood if intent else None,
            "pacing": intent.pacing if intent else None,
            "lighting": intent.lighting if intent else None,
            "audience_experience": intent.audience_experience if intent else None,
            "ending_tone": intent.ending_tone if intent else None,
        }

        prompt = (
            f"Title: {story.title}\n"
            f"Creative Intent: {intent_summary}\n\n"
            f"Story Text:\n{story_text}\n\n"
            "Extract characters (CHAR-001...), locations (LOC-001...), chronological narrative events (E001...), "
            "and story_structure as strict JSON."
        )

        payload, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": INTELLIGENCE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMStoryIntelligencePayload,
            engine="story_intelligence",
            operation="extract_entities",
            project_id=project_id,
            temperature=0.25,
            max_tokens=2600,
        )

        # Replace previous extracted entities cleanly for this project
        await self.session.execute(delete(Character).where(Character.project_id == project_id))
        await self.session.execute(delete(Location).where(Location.project_id == project_id))
        await self.session.execute(delete(NarrativeEvent).where(NarrativeEvent.project_id == project_id))

        chars: list[Character] = []
        for idx, ch in enumerate(payload.characters, start=1):
            row = Character(
                project_id=project_id,
                character_code=ch.character_code or f"CHAR-{idx:03d}",
                name=ch.name.strip(),
                role=ch.role.strip(),
                age_range=ch.age_range,
                physical_appearance=ch.physical_appearance.strip(),
                clothing=ch.clothing,
                personality=ch.personality.strip(),
                voice_characteristics=ch.voice_characteristics.strip(),
                relationships=ch.relationships,
                emotional_development=ch.emotional_development,
                uncertain_details=ch.uncertain_details,
            )
            self.session.add(row)
            chars.append(row)

        locs: list[Location] = []
        for idx, loc in enumerate(payload.locations, start=1):
            row = Location(
                project_id=project_id,
                location_code=loc.location_code or f"LOC-{idx:03d}",
                name=loc.name.strip(),
                description=loc.description.strip(),
                environment=loc.environment,
                lighting_characteristics=loc.lighting_characteristics,
                time_of_day=loc.time_of_day,
                visual_elements=loc.visual_elements,
            )
            self.session.add(row)
            locs.append(row)

        events: list[NarrativeEvent] = []
        sorted_events = sorted(payload.events, key=lambda e: e.timeline_position)
        for idx, ev in enumerate(sorted_events, start=1):
            row = NarrativeEvent(
                project_id=project_id,
                event_id=ev.event_id or f"E{idx:03d}",
                description=ev.description.strip(),
                characters=ev.characters,
                location=ev.location,
                timeline_position=ev.timeline_position,
                narrative_role=ev.narrative_role.strip(),
                narrative_importance=float(ev.narrative_importance),
                cause=ev.cause,
                consequence=ev.consequence,
                emotion=ev.emotion.strip(),
                intensity=float(ev.intensity),
                continuity_info=ev.continuity_info,
            )
            self.session.add(row)
            events.append(row)

        structure_dict = payload.story_structure.model_dump()
        story.structure_json = {**(story.structure_json or {}), **structure_dict}
        await self.session.flush()

        return chars, locs, events, structure_dict
