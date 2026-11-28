"""Narrative analysis endpoint triggering Story Intelligence + NetworkX Emotion Graph + Reasoning preview."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.db.models.domain import Character, CreativeIntent, Location, NarrativeEvent, NarrativeGraph
from app.dependencies import AppSettings, DbSession
from app.engines.cinematic_reasoning import CinematicReasoningEngine
from app.engines.narrative_emotion import NarrativeEmotionEngine
from app.engines.story_intelligence import StoryIntelligenceEngine
from app.services.llm_service import LLMService

router = APIRouter(prefix="/narrative", tags=["narrative"])


class NarrativeAnalyzeRequest(BaseModel):
    project_id: uuid.UUID
    story_id: uuid.UUID | None = None
    include_reasoning_preview: bool = True


class NarrativeAnalyzeResponse(BaseModel):
    project_id: uuid.UUID
    characters: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    graph: dict[str, Any] = Field(default_factory=dict)
    reasoning_preview: dict[str, Any] | None = None


def _serialize_results(
    project_id: uuid.UUID,
    characters: list[Character],
    locations: list[Location],
    events: list[NarrativeEvent],
    graph_row: NarrativeGraph,
    reasoning_preview: dict[str, Any] | None = None,
) -> NarrativeAnalyzeResponse:
    return NarrativeAnalyzeResponse(
        project_id=project_id,
        characters=[
            {
                "id": str(c.id),
                "character_code": c.character_code,
                "name": c.name,
                "role": c.role,
                "age_range": c.age_range,
                "physical_appearance": c.physical_appearance,
                "clothing": c.clothing,
                "personality": c.personality,
                "voice_characteristics": c.voice_characteristics,
                "relationships": c.relationships or [],
                "emotional_development": c.emotional_development,
                "uncertain_details": c.uncertain_details or [],
            }
            for c in characters
        ],
        locations=[
            {
                "id": str(loc.id),
                "location_code": loc.location_code,
                "name": loc.name,
                "description": loc.description,
                "environment": loc.environment,
                "lighting_characteristics": loc.lighting_characteristics,
                "time_of_day": loc.time_of_day,
                "visual_elements": loc.visual_elements or [],
            }
            for loc in locations
        ],
        events=[
            {
                "id": str(e.id),
                "event_id": e.event_id,
                "description": e.description,
                "characters": e.characters,
                "location": e.location,
                "timeline_position": e.timeline_position,
                "narrative_role": e.narrative_role,
                "narrative_importance": e.narrative_importance,
                "cause": e.cause,
                "consequence": e.consequence,
                "emotion": e.emotion,
                "intensity": e.intensity,
                "continuity_info": e.continuity_info or {},
            }
            for e in sorted(events, key=lambda x: x.timeline_position)
        ],
        graph={
            "id": str(graph_row.id),
            "nodes": graph_row.nodes,
            "edges": graph_row.edges,
            "diagnostics": graph_row.diagnostics,
            "story_structure": graph_row.story_structure,
        },
        reasoning_preview=reasoning_preview,
    )


@router.post(
    "/analyze",
    response_model=NarrativeAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract story intelligence entities and build NetworkX narrative/emotion graph",
)
async def analyze_narrative(
    payload: NarrativeAnalyzeRequest,
    session: DbSession,
    settings: AppSettings,
) -> NarrativeAnalyzeResponse:
    llm = LLMService(session=session, settings=settings)
    intel_engine = StoryIntelligenceEngine(session=session, llm_service=llm)
    characters, locations, events, story_structure = await intel_engine.extract_entities(
        project_id=payload.project_id,
        story_id=payload.story_id,
    )

    graph_engine = NarrativeEmotionEngine(session=session)
    graph_row = await graph_engine.build_and_analyze(
        project_id=payload.project_id,
        characters=characters,
        locations=locations,
        events=events,
        story_structure=story_structure,
    )

    reasoning_preview: dict[str, Any] | None = None
    if payload.include_reasoning_preview and events:
        intent = (
            await session.execute(select(CreativeIntent).where(CreativeIntent.project_id == payload.project_id))
        ).scalar_one_or_none()
        intent_dict = {
            "visual_style": intent.visual_style if intent else None,
            "overall_mood": intent.overall_mood if intent else None,
            "pacing": intent.pacing if intent else None,
            "lighting": intent.lighting if intent else None,
            "camera_preferences": intent.camera_preferences if intent else None,
        }
        peak_event = max(events, key=lambda e: e.intensity)
        reasoning_engine = CinematicReasoningEngine(settings=settings, llm_service=llm)
        decision = await reasoning_engine.recommend_treatment(
            project_id=payload.project_id,
            beat_description=peak_event.description,
            emotion=peak_event.emotion,
            intensity=peak_event.intensity,
            narrative_role=peak_event.narrative_role,
            creative_intent=intent_dict,
        )
        await session.commit()
        reasoning_preview = {
            "peak_event_id": peak_event.event_id,
            "decision": decision.model_dump(),
        }

    return _serialize_results(
        payload.project_id, characters, locations, events, graph_row, reasoning_preview
    )


@router.get(
    "/{project_id}",
    response_model=NarrativeAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch persisted narrative entities and NetworkX graph for a project",
)
async def get_narrative_analysis(
    project_id: uuid.UUID,
    session: DbSession,
) -> NarrativeAnalyzeResponse:
    graph_row = (
        await session.execute(select(NarrativeGraph).where(NarrativeGraph.project_id == project_id))
    ).scalar_one_or_none()
    if graph_row is None:
        raise NotFoundError("Narrative analysis has not been run yet.", code="NARRATIVE_NOT_FOUND")

    characters = (await session.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
    locations = (await session.execute(select(Location).where(Location.project_id == project_id))).scalars().all()
    events = (await session.execute(select(NarrativeEvent).where(NarrativeEvent.project_id == project_id))).scalars().all()
    return _serialize_results(project_id, list(characters), list(locations), list(events), graph_row)
