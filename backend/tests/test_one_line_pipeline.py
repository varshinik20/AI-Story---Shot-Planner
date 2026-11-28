"""End-to-end automated One-Line Idea -> Story -> CINEMIND Shot Planner -> PDF tests (Section 17)."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.domain import Character, Location, NarrativeGraph, Scene, Shot, Story
from app.services.llm_service import LLMCallResult, LLMService


class _PipelineQueueAdapter:
    """Deterministic LLM adapter returning scripted structured payloads per stage."""

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
            input_tokens=240,
            output_tokens=180,
            execution_time_ms=90,
            estimated_cost_usd=0.0021,
            request_id="req-one-line",
        )


def _build_prompt_payload_sequence(
    *,
    title: str,
    genre: str,
    logline: str,
    theme: str,
    protagonist: str,
    companion: str,
    loc1: str,
    loc2: str,
    dialogue_line: str,
) -> list[dict]:
    developed_story = (
        f"{protagonist} stood inside {loc1} staring toward the horizon. "
        f'{protagonist} whispered, "{dialogue_line}" '
        f"{companion} arrived beside {protagonist} as tension rose toward {loc2}. "
        f"Crossing the threshold into {loc2}, {protagonist} embraced the turning point and found quiet resolution."
    )
    return [
        # 1. Concept Expansion & Story Development
        {
            "title": title,
            "logline": logline,
            "genre": genre,
            "central_theme": theme,
            "synopsis": f"In {loc1}, {protagonist} sets out toward {loc2} and transforms forever.",
            "developed_story": developed_story,
            "beginning_summary": f"{protagonist} contemplates the call inside {loc1}.",
            "middle_summary": f"{companion} challenges {protagonist} as stakes escalate.",
            "ending_summary": f"At {loc2}, {protagonist} achieves emotional closure.",
            "dialogue_present": True,
            "visual_style": "Atmospheric Cinematic Realism",
            "colour_palette": "Warm amber highlights against cool slate shadows",
            "overall_atmosphere": "Intimate lyrical tension",
            "overall_mood": "Hopeful yet poignant",
            "pacing": "Measured lyrical build-up",
            "lighting": "Natural twilight transitioning to warm dawn",
            "camera_preferences": "Intimate tracking frames paired with revealing wide compositions",
            "character_treatment": f"Subjective close-ups tracking {protagonist}",
            "audience_experience": "Deep emotional empathy",
            "ending_tone": "Uplifting bittersweet resolution",
            "desired_ending_experience": "Quiet lasting wonder",
        },
        # 2. StoryIntelligenceEngine
        {
            "characters": [
                {
                    "character_code": "CHAR-001",
                    "name": protagonist,
                    "role": "Protagonist",
                    "age_range": "18-24",
                    "physical_appearance": "Expressive eyes, weathered coat",
                    "clothing": "Simple layered traveler attire",
                    "personality": "Determined, observant",
                    "voice_characteristics": "Quiet but resolute",
                    "emotional_development": "Moves from doubt to conviction",
                    "uncertain_details": [],
                },
                {
                    "character_code": "CHAR-002",
                    "name": companion,
                    "role": "Supporting Character",
                    "age_range": "30-45",
                    "physical_appearance": "Steady posture, warm gaze",
                    "clothing": "Practical earth-toned cloak",
                    "personality": "Guarded yet caring",
                    "voice_characteristics": "Measured low cadence",
                    "emotional_development": "Learns to trust",
                    "uncertain_details": [],
                },
            ],
            "locations": [
                {
                    "location_code": "LOC-001",
                    "name": loc1,
                    "description": f"Quiet starting threshold of {loc1}.",
                    "environment": "Still air, soft natural acoustics",
                    "lighting_characteristics": "Soft overcast morning light",
                    "time_of_day": "Morning",
                    "visual_elements": ["Threshold archway", "Dust motes"],
                },
                {
                    "location_code": "LOC-002",
                    "name": loc2,
                    "description": f"Expansive climax space of {loc2}.",
                    "environment": "Open horizon and resonant wind",
                    "lighting_characteristics": "Golden rim lighting",
                    "time_of_day": "Dusk",
                    "visual_elements": ["Open vista", "Distant silhouettes"],
                },
            ],
            "events": [
                {
                    "event_id": "E001",
                    "description": f"{protagonist} prepares inside {loc1} and speaks softly.",
                    "characters": [protagonist],
                    "location": loc1,
                    "timeline_position": 1,
                    "narrative_role": "opening_setup",
                    "narrative_importance": 0.7,
                    "cause": "Longing for change",
                    "consequence": "Sets journey in motion",
                    "emotion": "Suspense",
                    "intensity": 0.5,
                    "continuity_info": {"state": "Start posture"},
                },
                {
                    "event_id": "E002",
                    "description": f"{companion} confronts {protagonist} en route to {loc2}.",
                    "characters": [protagonist, companion],
                    "location": loc2,
                    "timeline_position": 2,
                    "narrative_role": "climax",
                    "narrative_importance": 0.95,
                    "cause": "Stepping beyond fear",
                    "consequence": "Transformation achieved",
                    "emotion": "Happiness",
                    "intensity": 0.9,
                    "continuity_info": {"state": "Resolved"},
                },
            ],
            "story_structure": {
                "inciting_incident": "Quiet longing stirs action.",
                "rising_action": "Threshold crossing against fear.",
                "climax": "Moment of courage",
                "resolution": "New beginning unfolds.",
                "pacing_arc": "escalating",
                "dialogue_present": True,
            },
        },
        # 3. ProductionEngine Scene Breakdown (2 dynamic scenes)
        {
            "scenes": [
                {
                    "scene_id": "S01",
                    "scene_order": 1,
                    "title": f"Awakening in {loc1}",
                    "location": loc1,
                    "time_of_day": "Morning",
                    "summary": f"{protagonist} whispers resolve inside {loc1}.",
                    "event_ids": ["E001"],
                },
                {
                    "scene_id": "S02",
                    "scene_order": 2,
                    "title": f"Arrival at {loc2}",
                    "location": loc2,
                    "time_of_day": "Dusk",
                    "summary": f"{protagonist} and {companion} face the turning point at {loc2}.",
                    "event_ids": ["E002"],
                },
            ]
        },
        # 4. Shots for Scene S01
        {
            "shots": [
                {
                    "shot_id": "S01_SH01",
                    "shot_order": 1,
                    "duration_seconds": 4,
                    "framing": "Wide Shot (WS)",
                    "camera": {"angle": "Eye Level", "movement": "Slow Push-In"},
                    "characters": [protagonist],
                    "location": loc1,
                    "visual_description": f"{protagonist} gazes out from {loc1} at dawn.",
                    "dialogue": [],
                    "emotion": "Suspense",
                    "sound": "Quiet ambient room tone and distant breeze.",
                },
                {
                    "shot_id": "S01_SH02",
                    "shot_order": 2,
                    "duration_seconds": 5,
                    "framing": "Close-Up (CU)",
                    "camera": {"angle": "Eye Level", "movement": "Static"},
                    "characters": [protagonist],
                    "location": loc1,
                    "visual_description": f"Tight expression on {protagonist} deciding to leave.",
                    "dialogue": [
                        {
                            "speaker": protagonist,
                            "exact_line": dialogue_line,
                            "delivery": "Soft whisper",
                        }
                    ],
                    "emotion": "Hope",
                    "sound": "Gentle breath and subtle string sustain.",
                },
            ]
        },
        # 5. Shots for Scene S02
        {
            "shots": [
                {
                    "shot_id": "S02_SH01",
                    "shot_order": 1,
                    "duration_seconds": 6,
                    "framing": "Medium-Wide Shot",
                    "camera": {"angle": "Low Angle", "movement": "Tracking Shot"},
                    "characters": [protagonist, companion],
                    "location": loc2,
                    "visual_description": f"{protagonist} and {companion} step together into golden wind at {loc2}.",
                    "dialogue": [],
                    "emotion": "Happiness",
                    "sound": "Warm swelling score and open horizon breeze.",
                }
            ]
        },
    ]


@pytest.mark.parametrize(
    ("idea", "title", "genre", "protagonist", "companion", "loc1", "loc2", "dialogue_line"),
    [
        (
            "The girl chased her dream.",
            "Chasing the Painted Horizon",
            "Coming-of-Age Drama",
            "Anya",
            "Coach Dev",
            "Attic Studio",
            "City Stadium",
            "I will not stop running now.",
        ),
        (
            "A boy discovers a hidden kingdom.",
            "Crown Beneath the Moss",
            "Fantasy Adventure",
            "Kian",
            "Elder Lyra",
            "Mossy Hollow",
            "Crystal Citadel",
            "Every stone here remembers our names.",
        ),
        (
            "A robot falls in love with its creator.",
            "Pulse of Glass",
            "Science Fiction Romance",
            "Unit Seven",
            "Dr. Elena Vance",
            "Robotics Workshop",
            "Glass Conservatory",
            "Even circuits learn how silence aches.",
        ),
        (
            "A mother searches for her missing daughter.",
            "Lanterns Along the Coast",
            "Mystery Thriller",
            "Nora",
            "Harbor Warden",
            "Foggy Pier",
            "Cliffside Lighthouse",
            "Leave the lamp lit until dawn.",
        ),
        (
            "The last tree on Earth begins to speak.",
            "Roots of the Final Song",
            "Speculative Drama",
            "Arjun",
            "The Ancient Oak",
            "Dust Bowl Courtyard",
            "Glass Sanctuary",
            "Listen closely before the wind forgets.",
        ),
        (
            "A village forgets the meaning of happiness.",
            "The Bellmaker's Gift",
            "Fable Drama",
            "Mira",
            "Old Tomas",
            "Silent Square",
            "Hilltop Belfry",
            "Ring it once so they remember warmth.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_one_line_prompts_end_to_end_story_planner_and_pdf(
    client: AsyncClient,
    db_session: AsyncSession,
    idea: str,
    title: str,
    genre: str,
    protagonist: str,
    companion: str,
    loc1: str,
    loc2: str,
    dialogue_line: str,
) -> None:
    """Section 17: Verify one-line ideas generate complete stories, characters, locations, scenes, shots, and valid PDF."""
    adapter = _PipelineQueueAdapter(
        _build_prompt_payload_sequence(
            title=title,
            genre=genre,
            logline=f"A cinematic journey inspired by: {idea}",
            theme="Courage transforms longing into action.",
            protagonist=protagonist,
            companion=companion,
            loc1=loc1,
            loc2=loc2,
            dialogue_line=dialogue_line,
        )
    )

    with patch("app.api.v1.endpoints.chat.LLMService") as mock_llm_cls:
        mock_llm_cls.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=adapter
        )
        res = await client.post(
            "/api/v1/chat/message",
            json={"message": idea, "input_source": "text"},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["planner_ready"] is True
    assert body["workflow_stage"] == "approved_for_export"
    assert body["intake_state"]["story_title"] == title
    assert body["scene_count"] == 2
    assert body["shot_count"] == 3
    assert body["total_runtime_seconds"] == 15  # 4 + 5 + 6
    assert title in body["assistant_message"]
    assert "What would you like to call" not in body["assistant_message"]

    project_id = body["project_id"]

    # Verify PostgreSQL persistence across Story, Graph, Characters, Locations, Scenes, Shots
    story = (await db_session.execute(select(Story).where(Story.project_id == project_id))).scalar_one()
    assert story.title == title
    assert story.status == "approved"
    assert story.approved_content and dialogue_line in story.approved_content

    chars = (await db_session.execute(select(Character).where(Character.project_id == project_id))).scalars().all()
    locs = (await db_session.execute(select(Location).where(Location.project_id == project_id))).scalars().all()
    scenes = (await db_session.execute(select(Scene).where(Scene.project_id == project_id))).scalars().all()
    shots = (await db_session.execute(select(Shot).where(Shot.project_id == project_id))).scalars().all()
    graph = (await db_session.execute(select(NarrativeGraph).where(NarrativeGraph.project_id == project_id))).scalar_one()

    assert len(chars) == 2
    assert len(locs) == 2
    assert len(scenes) == 2
    assert {s.shot_id for s in shots} == {"S01_SH01", "S01_SH02", "S02_SH01"}
    assert sum(s.duration_seconds for s in shots) == 15
    assert graph.diagnostics["node_count"] >= 4

    # Verify PDF export succeeds with dynamic content matching Reference Structure
    pdf_res = await client.get(f"/api/v1/planner/export/{project_id}")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(pdf_res.content))
    full_text = " ".join("\n".join(page.extract_text() or "" for page in reader.pages).split())
    assert title in full_text
    assert "2 SCENES | 3 SHOTS | 1 DIALOGUE LINE | 15 SECONDS" in full_text
    assert protagonist in full_text
    assert loc1 in full_text
    assert "S01_SH01" in full_text
    assert "S02_SH01" in full_text
    assert dialogue_line in full_text


@pytest.mark.asyncio
async def test_greeting_clarification_and_followup_edit_and_single_shot_regenerate(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Empty/greeting asks one concise clarification; follow-up edit and single-shot regenerate work cleanly."""
    # 1. Pure greeting returns concise clarification without calling LLM
    greet = await client.post(
        "/api/v1/chat/message",
        json={"message": "Hi", "input_source": "text"},
    )
    assert greet.status_code == 200
    assert greet.json()["planner_ready"] is False
    assert greet.json()["intent"] == "clarification"

    # 2. Generate full planner from one-line voice idea, then rename title via chat follow-up & regenerate one shot
    adapter_seq = _build_prompt_payload_sequence(
        title="Original Dream",
        genre="Drama",
        logline="A young runner chases the dawn.",
        theme="Persistence reveals strength.",
        protagonist="Lina",
        companion="Sora",
        loc1="Narrow Alley",
        loc2="Open Bridge",
        dialogue_line="We start before sunrise.",
    ) + [
        # Follow-up title rename payload
        {
            "updated_title": "Starlight Sprint",
            "updated_genre": "Inspirational Sports Drama",
            "updated_visual_style": None,
            "updated_story_text": None,
            "rebuild_scenes_and_shots": False,
            "assistant_reply": "Updated the title to Starlight Sprint and refined genre.",
        },
        # Single shot regenerate payload
        {
            "shots": [
                {
                    "shot_id": "S01_SH01",
                    "shot_order": 1,
                    "duration_seconds": 5,
                    "framing": "Medium Close-Up (MCU)",
                    "camera": {"angle": "Low Angle", "movement": "Slow Push-In"},
                    "characters": ["Lina"],
                    "location": "Narrow Alley",
                    "visual_description": "Lina laces her shoes as golden streetlamps flicker.",
                    "dialogue": [],
                    "emotion": "Determination",
                    "sound": "Crisp shoelace pull and distant train rumble.",
                }
            ]
        },
    ]
    adapter = _PipelineQueueAdapter(adapter_seq)

    with (
        patch("app.api.v1.endpoints.chat.LLMService") as mock_chat_llm,
        patch("app.api.v1.endpoints.shots.LLMService") as mock_shot_llm,
    ):
        mock_chat_llm.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=adapter
        )
        mock_shot_llm.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=adapter
        )

        r_gen = await client.post(
            "/api/v1/chat/message",
            json={"message": "The girl chased her dream.", "input_source": "voice"},
        )
        assert r_gen.status_code == 200
        d_gen = r_gen.json()
        assert d_gen["planner_ready"] is True

        # Follow-up creator edit in same conversation
        r_edit = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Change title to Starlight Sprint",
                "input_source": "text",
                "project_id": d_gen["project_id"],
                "conversation_id": d_gen["conversation_id"],
            },
        )
        assert r_edit.status_code == 200
        assert r_edit.json()["intake_state"]["story_title"] == "Starlight Sprint"

        # Single shot regenerate keeps shot_id S01_SH01 and updates framing
        ws_res = await client.get(f"/api/v1/planner/{d_gen['project_id']}")
        assert ws_res.status_code == 200
        first_shot_uuid = ws_res.json()["scenes"][0]["shots"][0]["id"]

        r_regen = await client.post(
            f"/api/v1/shots/{first_shot_uuid}/regenerate",
            json={"instruction": "Make opening shot tighter on her determination"},
        )
        assert r_regen.status_code == 200
        assert r_regen.json()["shot_id"] == "S01_SH01"
        assert r_regen.json()["framing"] == "Medium Close-Up (MCU)"
