"""Phases G & H tests: Progressive scene/shot generation, dialogue guard, What-If, and validation."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.domain import Character, ContinuityState, CreativeIntent, Location, NarrativeEvent, Story
from app.db.models.project import Project
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
            input_tokens=320,
            output_tokens=240,
            execution_time_ms=130,
            estimated_cost_usd=0.0032,
            request_id="req-gh-test",
        )


@pytest.mark.asyncio
async def test_progressive_scenes_shots_what_if_and_validation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    project = Project(title="The Edge of Dawn", description="Cliff fall thriller")
    db_session.add(project)
    await db_session.flush()

    story = Story(
        project_id=project.id,
        title="The Edge of Dawn",
        visual_style="Realistic Cinematic Film",
        premise="The girl ran toward the cliff edge and fell down.",
        source_type="intake_confirmed",
        original_content="The girl ran toward the cliff edge and fell down.",
        working_content='Elena ran toward the cliff edge and fell down. Reaching a root she whispered, "Hold on."',
        approved_content='Elena ran toward the cliff edge and fell down. Reaching a root she whispered, "Hold on."',
        status="approved",
    )
    intent = CreativeIntent(
        project_id=project.id,
        visual_style="Realistic Cinematic Film",
        overall_mood="Tense",
        pacing="Urgent",
        lighting="Cold mist",
        camera_preferences="Handheld tracking",
        audience_experience="Children",  # Intentional trigger for audience warning test
        ending_tone="Hopeful survival",
        is_complete=True,
    )
    char = Character(
        project_id=project.id,
        character_code="CHAR-001",
        name="Elena",
        role="Protagonist",
        physical_appearance="Young runner in mist",
        personality="Determined",
        voice_characteristics="Breathless whisper",
    )
    loc = Location(
        project_id=project.id,
        location_code="LOC-001",
        name="Coastal Cliff Ridge",
        description="Wet slate ledge above misty gorge",
        time_of_day="Dawn",
    )
    ev1 = NarrativeEvent(
        project_id=project.id,
        event_id="E001",
        description="Elena sprints toward the cliff edge.",
        characters=["Elena"],
        location="Coastal Cliff Ridge",
        timeline_position=1,
        narrative_role="inciting_incident",
        emotion="anxiety",
        intensity=0.5,
    )
    ev2 = NarrativeEvent(
        project_id=project.id,
        event_id="E002",
        description="Elena slips and falls down over the edge.",
        characters=["Elena"],
        location="Coastal Cliff Ridge",
        timeline_position=2,
        narrative_role="climax",
        emotion="terror",
        intensity=0.95,
    )
    db_session.add_all([story, intent, char, loc, ev1, ev2])
    await db_session.commit()

    scene_payload = {
        "scenes": [
            {
                "scene_id": "SC-001",
                "scene_order": 1,
                "title": "Run to the Edge",
                "location": "Coastal Cliff Ridge",
                "time_of_day": "Dawn",
                "summary": "Elena sprints toward the slick precipice.",
                "event_ids": ["E001"],
            },
            {
                "scene_id": "SC-002",
                "scene_order": 2,
                "title": "The Fall",
                "location": "Coastal Cliff Ridge",
                "time_of_day": "Dawn",
                "summary": "Slate breaks under her boots and she falls down toward the mist.",
                "event_ids": ["E002"],
            },
        ]
    }
    shots_sc1_payload = {
        "shots": [
            {
                "shot_id": "SC01-S01",
                "shot_order": 1,
                "duration_seconds": 4,
                "framing": "Wide Tracking Shot",
                "camera": {"angle": "Eye Level", "movement": "Handheld Tracking"},
                "characters": ["Elena"],
                "location": "Coastal Cliff Ridge",
                "visual_description": "Elena races through cold sea mist toward the ridge edge.",
                "dialogue": [
                    {"speaker": "Elena", "exact_line": "I should not run here!", "delivery": "hallucinated"}
                ],
                "emotion": "anxiety",
                "sound": "Footsteps slapping wet slate, howling wind",
            },
            {
                "shot_id": "SC01-S02",
                "shot_order": 2,
                "duration_seconds": 3,
                "framing": "Close-Up",
                "camera": {"angle": "Low Angle", "movement": "Dolly Push-In"},
                "characters": ["Elena"],
                "location": "Coastal Cliff Ridge",
                "visual_description": "Muddy boots skid near crumbling rock at the cliff brink.",
                "dialogue": [],
                "emotion": "fear",
                "sound": "Gravel sliding into the void",
            },
        ]
    }
    whatif_payload = {
        "alternatives": [
            {
                "label": "Option A",
                "title": "Overhead Vertigo Drop",
                "framing": "Overhead Extreme Close-Up",
                "camera_angle": "Overhead Bird's Eye",
                "camera_movement": "Crane Tilt-Down",
                "duration_seconds": 2,  # Intentionally <3s with Crane to test feasibility check!
                "visual_description": "Terrifying brutal plunge framing down the sheer cliff wall.",
                "emotion": "terror",
                "sound": "Sudden silence then wind rush",
                "audience_experience_effect": "Heightens visceral dread and sudden vertical shock.",
            },
            {
                "label": "Option B",
                "title": "Measured Wide Edge",
                "framing": "Wide Shot",
                "camera_angle": "Eye Level",
                "camera_movement": "Static",
                "duration_seconds": 5,
                "visual_description": "Clean wide view of Elena catching hold above mist.",
                "emotion": "suspense",
                "sound": "Wind and waves below",
                "audience_experience_effect": "Softer stylized tension suitable for wider audiences.",
            },
        ]
    }

    with (
        patch("app.api.v1.endpoints.scenes.LLMService") as mock_scenes_llm,
        patch("app.api.v1.endpoints.shots.LLMService") as mock_shots_llm,
    ):
        scenes_adapter = _QueueAdapter([scene_payload])
        shots_adapter = _QueueAdapter([shots_sc1_payload, whatif_payload])

        mock_scenes_llm.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=scenes_adapter
        )
        mock_shots_llm.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=shots_adapter
        )

        # 1. Propose scenes (no shots created yet, unapproved by default)
        s_res = await client.post("/api/v1/scenes/generate", json={"project_id": str(project.id)})
        assert s_res.status_code == 200
        scenes_data = s_res.json()
        assert len(scenes_data) == 2
        assert scenes_data[0]["is_approved"] is False
        assert scenes_data[0]["shots"] == []

        sc1_uuid = scenes_data[0]["id"]
        sc2_uuid = scenes_data[1]["id"]

        # 2. Generating shots before scene approval must be rejected cleanly with 409
        blocked_res = await client.post("/api/v1/shots/generate", json={"scene_uuid": sc1_uuid})
        assert blocked_res.status_code == 409

        # 3. Approve Scene 1 only, then generate shots strictly for Scene 1
        app_res = await client.post(
            "/api/v1/scenes/approve",
            json={"project_id": str(project.id), "scene_ids": [sc1_uuid]},
        )
        assert app_res.status_code == 200

        sh_res = await client.post("/api/v1/shots/generate", json={"scene_uuid": sc1_uuid})
        assert sh_res.status_code == 200
        sc1_with_shots = sh_res.json()
        assert sc1_with_shots["shots_generated"] is True
        assert len(sc1_with_shots["shots"]) == 2
        # Verify dialogue guard stripped the hallucinated dialogue line not in approved story!
        assert sc1_with_shots["shots"][0]["dialogue"] == []

        # Scene 2 still has no shots generated
        all_scenes = (await client.get(f"/api/v1/scenes/{project.id}")).json()
        sc2_state = next(s for s in all_scenes if s["id"] == sc2_uuid)
        assert sc2_state["shots_generated"] is False

        # Continuity state snapshot was persisted for Scene 1
        c_states = (await db_session.execute(select(ContinuityState))).scalars().all()
        assert len(c_states) >= 1

        # 4. What-If alternatives & apply on shot 2 only
        target_shot_uuid = sc1_with_shots["shots"][1]["id"]
        alt_res = await client.post(
            f"/api/v1/shots/{target_shot_uuid}/alternatives",
            json={"creative_prompt": "Make the brink moment more terrifying."},
        )
        assert alt_res.status_code == 200
        alts = alt_res.json()
        assert len(alts) == 2

        apply_res = await client.post(
            f"/api/v1/shots/{target_shot_uuid}/alternatives/{alts[0]['id']}/apply"
        )
        assert apply_res.status_code == 200
        assert apply_res.json()["shot"]["framing"] == "Overhead Extreme Close-Up"

        # Direct PATCH edit (adding verbatim line "Hold on." from approved story)
        patch_res = await client.patch(
            f"/api/v1/shots/{target_shot_uuid}",
            json={
                "dialogue": [{"speaker": "Elena", "exact_line": "Hold on.", "delivery": "breathless whisper"}]
            },
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["dialogue"][0]["exact_line"] == "Hold on."

    # 5. Run Continuity + Audience + Feasibility validation
    val_res = await client.post("/api/v1/validation/run", json={"project_id": str(project.id)})
    assert val_res.status_code == 200
    val_data = val_res.json()
    categories = {i["category"] for i in val_data["issues"]}
    assert "continuity" in categories  # Scene 2 has no shots yet
    assert "audience_experience" in categories  # Children audience + intense/terrifying warning
    assert "feasibility" in categories  # Crane movement < 3s
