"""Phases E & F tests: Story Intelligence, NetworkX Graph, Hybrid Cinematic Reasoning."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models.domain import CreativeIntent, Story
from app.db.models.project import Project
from app.engines.cinematic_reasoning.engine import CinematicReasoningEngine, ShotTreatmentCandidate
from app.services.llm_service import LLMCallResult, LLMService


class _QueueAdapter:
    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
        json_mode: bool,
    ) -> LLMCallResult:
        return LLMCallResult(
            content=json.dumps(self._payloads.pop(0)),
            model="gpt-4o",
            input_tokens=300,
            output_tokens=200,
            execution_time_ms=110,
            estimated_cost_usd=0.00275,
            request_id="req-ef-test",
        )


@pytest.mark.asyncio
async def test_cinematic_reasoning_formula_weights_and_continuity_penalty(db_session: AsyncSession) -> None:
    settings = Settings(DATABASE_URL=str(db_session.bind.url), OPENAI_API_KEY="test")
    llm = LLMService(session=db_session, settings=settings, adapter=_QueueAdapter([]))
    engine = CinematicReasoningEngine(settings=settings, llm_service=llm)

    # Identical framing/angle to previous shot should suffer jump-cut continuity penalty
    c1 = ShotTreatmentCandidate(
        label="Option A",
        framing="Medium Shot",
        camera_angle="Eye Level",
        camera_movement="Static",
        duration_seconds=8,
        lighting_note="Cold desaturated mist",
        rationale="Static observation",
    )
    # Climax close-up with tracking movement should score significantly higher
    c2 = ShotTreatmentCandidate(
        label="Option B",
        framing="Close-Up",
        camera_angle="Low Angle",
        camera_movement="Handheld Tracking",
        duration_seconds=4,
        lighting_note="Cold desaturated mist rim light",
        rationale="Urgent close-up maximizes fear during fall.",
    )
    prev = {"framing": "Medium Shot", "camera": {"angle": "Eye Level"}}
    intent = {"camera_preferences": "Intimate handheld tracking", "pacing": "Urgent", "lighting": "Cold mist"}

    s1 = engine.score_candidate(c1, emotion="terror", intensity=0.9, narrative_role="climax", creative_intent=intent, previous_shot=prev)
    s2 = engine.score_candidate(c2, emotion="terror", intensity=0.9, narrative_role="climax", creative_intent=intent, previous_shot=prev)

    assert s2.weighted_total > s1.weighted_total
    assert any("jump cut" in note.lower() for note in s1.validation_notes)
    expected_total = round(
        0.35 * s2.emotion_score + 0.25 * s2.narrative_score + 0.20 * s2.director_score + 0.20 * s2.continuity_score,
        4,
    )
    assert s2.weighted_total == expected_total


@pytest.mark.asyncio
async def test_narrative_analyze_builds_networkx_graph_and_diagnostics(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    project = Project(title="The Edge of Dawn", description="Cliff fall story")
    db_session.add(project)
    await db_session.flush()

    story = Story(
        project_id=project.id,
        title="The Edge of Dawn",
        visual_style="Realistic Cinematic Film",
        premise="The girl ran toward the cliff edge and fell down.",
        source_type="intake_confirmed",
        original_content="The girl ran toward the cliff edge and fell down.",
        working_content="Elena ran along the ridge toward the cliff edge, slipped on wet slate, and fell down before catching a root.",
        approved_content="Elena ran along the ridge toward the cliff edge, slipped on wet slate, and fell down before catching a root.",
        status="approved",
    )
    intent = CreativeIntent(
        project_id=project.id,
        visual_style="Realistic Cinematic Film",
        overall_mood="Tense & Suspenseful",
        pacing="Urgent & kinetic",
        lighting="Cold desaturated mist",
        camera_preferences="Handheld tracking",
        audience_experience="Mature Thriller / Drama",
        ending_tone="Hopeful survival",
        is_complete=True,
    )
    db_session.add_all([story, intent])
    await db_session.commit()

    adapter = _QueueAdapter(
        [
            {
                "characters": [
                    {
                        "character_code": "CHAR-001",
                        "name": "Elena",
                        "role": "protagonist",
                        "age_range": None,
                        "physical_appearance": "Young woman running in sea mist.",
                        "clothing": None,
                        "personality": "Determined, panicked under pressure",
                        "voice_characteristics": "Labored breathing; no spoken lines",
                        "relationships": [],
                        "emotional_development": "Panic -> shock -> determination",
                        "uncertain_details": ["Exact age not specified", "Wardrobe color unstated"],
                    }
                ],
                "locations": [
                    {
                        "location_code": "LOC-001",
                        "name": "Coastal Cliff Ridge",
                        "description": "Wet slate path ending in a sharp cliff drop over a misty gorge.",
                        "environment": "Exterior coastal cliffside",
                        "lighting_characteristics": "Cold desaturated morning mist",
                        "time_of_day": "Dawn",
                        "visual_elements": ["Wet slate", "Twisted root", "Swirling sea fog"],
                    }
                ],
                "events": [
                    {
                        "event_id": "E001",
                        "description": "Elena sprints along the wet ridge toward the cliff edge.",
                        "characters": ["Elena"],
                        "location": "Coastal Cliff Ridge",
                        "timeline_position": 1,
                        "narrative_role": "inciting_incident",
                        "narrative_importance": 0.8,
                        "cause": "Urgent flight through mist",
                        "consequence": "Approaches slippery drop-off",
                        "emotion": "anxiety",
                        "intensity": 0.45,
                        "continuity_info": {"position": "ridge path"},
                    },
                    {
                        "event_id": "E002",
                        "description": "Wet rock crumbles beneath her boots and she falls down over the cliff edge.",
                        "characters": ["Elena"],
                        "location": "Coastal Cliff Ridge",
                        "timeline_position": 2,
                        "narrative_role": "climax",
                        "narrative_importance": 1.0,
                        "cause": "Slick rock gives way",
                        "consequence": "Plummets toward gorge",
                        "emotion": "terror",
                        "intensity": 0.95,
                        "continuity_info": {"position": "airborne over cliff"},
                    },
                    {
                        "event_id": "E003",
                        "description": "She catches a twisted root jutting from the cliff face and looks up toward dawn.",
                        "characters": ["Elena"],
                        "location": "Coastal Cliff Ridge",
                        "timeline_position": 3,
                        "narrative_role": "resolution",
                        "narrative_importance": 0.9,
                        "cause": "Grasps exposed root mid-fall",
                        "consequence": "Survives above mist",
                        "emotion": "relief",
                        "intensity": 0.40,
                        "continuity_info": {"position": "hanging from root"},
                    },
                ],
                "story_structure": {
                    "inciting_incident": "Elena runs toward the cliff edge.",
                    "rising_action": "Mist obscures footing on slick slate.",
                    "climax": "She slips and falls down the cliff.",
                    "resolution": "She catches a root above the gorge.",
                    "pacing_arc": "rapid escalation then sharp breath",
                    "dialogue_present": False,
                },
            },
            {
                "candidates": [
                    {
                        "label": "Option A",
                        "framing": "Extreme Close-Up",
                        "camera_angle": "High Angle",
                        "camera_movement": "Handheld Tracking",
                        "duration_seconds": 3,
                        "lighting_note": "Cold desaturated mist",
                        "rationale": "Vertiginous drop perspective emphasizing peril.",
                    },
                    {
                        "label": "Option B",
                        "framing": "Wide Shot",
                        "camera_angle": "Eye Level",
                        "camera_movement": "Static",
                        "duration_seconds": 10,
                        "lighting_note": "Flat grey light",
                        "rationale": "Distant passive framing.",
                    },
                ]
            },
        ]
    )

    with patch("app.api.v1.endpoints.narrative.LLMService") as mock_llm_cls:
        mock_llm_cls.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=adapter
        )
        res = await client.post(
            "/api/v1/narrative/analyze",
            json={"project_id": str(project.id), "include_reasoning_preview": True},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["characters"]) == 1
        assert "Exact age not specified" in data["characters"][0]["uncertain_details"]
        assert len(data["events"]) == 3
        diag = data["graph"]["diagnostics"]
        assert diag["connected_components_count"] == 1
        assert len(diag["abrupt_emotional_transitions"]) >= 1
        assert len(diag["recommended_scene_clusters"]) >= 2
        assert data["reasoning_preview"]["peak_event_id"] == "E002"
        assert data["reasoning_preview"]["decision"]["selected"]["candidate"]["label"] == "Option A"
