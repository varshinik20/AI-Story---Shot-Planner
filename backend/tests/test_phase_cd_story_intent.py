"""Phases C & D integration tests: Story Development, Suggestions, Approval, and Creative Intent."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.domain import Story
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
            input_tokens=200,
            output_tokens=150,
            execution_time_ms=95,
            estimated_cost_usd=0.002,
            request_id="req-cd-test",
        )


@pytest.mark.asyncio
async def test_story_development_suggestion_accept_reject_approval_and_intent_interview(
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
        premise="The girl was running towards the edge of the cliff and fell down.",
        source_type="intake_confirmed",
        original_content="The girl was running towards the edge of the cliff and fell down.",
        working_content="The girl was running towards the edge of the cliff and fell down.",
        status="draft",
    )
    db_session.add(story)
    await db_session.commit()

    developed_text = (
        "Elena sprinted along the wet coastal path toward the cliff edge as mist swirled around her boots. "
        "Before she could halt, the slick rock gave way beneath her feet and she fell down into the gorge below. "
        "Moments later, clinging to a twisted root above the mist, she caught her breath and looked upward toward the dawn."
    )

    story_adapter = _QueueAdapter(
        [
            {
                "developed_story": developed_text,
                "beginning_summary": "Elena sprints toward the misty coastal cliff edge.",
                "middle_summary": "She loses footing on wet stone and falls down over the edge.",
                "ending_summary": "Clinging to a root above the gorge, she looks up at the dawn.",
                "dialogue_present": False,
                "suggestions": [
                    {
                        "section_title": "Opening Tension",
                        "original_passage": "mist swirled around her boots",
                        "suggested_passage": "freezing sea mist lashed against her ankles",
                        "explanation": "Sharpens physical urgency in the opening movement.",
                    },
                    {
                        "section_title": "Final Image",
                        "original_passage": "looked upward toward the dawn",
                        "suggested_passage": "gazed up as the first pale light broke over the ridge",
                        "explanation": "Matches the title motif visually.",
                    },
                ],
            }
        ]
    )

    with patch("app.api.v1.endpoints.stories.LLMService") as mock_story_llm:
        mock_story_llm.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=story_adapter
        )

        dev_res = await client.post(
            "/api/v1/stories/develop",
            json={"story_id": str(story.id)},
        )
        assert dev_res.status_code == 200
        dev_data = dev_res.json()
        assert dev_data["approved_content"] is None
        assert "cliff edge" in dev_data["working_content"]
        assert "fell down" in dev_data["working_content"]
        assert len(dev_data["suggestions"]) == 2
        assert len(dev_data["versions"]) == 2  # original + draft

        s1_id = dev_data["suggestions"][0]["id"]
        s2_id = dev_data["suggestions"][1]["id"]

        # Accept suggestion 1 -> updates working_content & adds edited version, approved_content remains None
        acc_res = await client.post(
            f"/api/v1/stories/suggestions/{s1_id}/decision",
            json={"decision": "accept"},
        )
        assert acc_res.status_code == 200
        acc_data = acc_res.json()
        assert "freezing sea mist lashed against her ankles" in acc_data["working_content"]
        assert acc_data["approved_content"] is None

        # Reject suggestion 2 -> original wording stays intact
        rej_res = await client.post(
            f"/api/v1/stories/suggestions/{s2_id}/decision",
            json={"decision": "reject"},
        )
        assert rej_res.status_code == 200
        rej_data = rej_res.json()
        assert "looked upward toward the dawn" in rej_data["working_content"]

        # Approve story -> sets approved_content & creates immutable approved version
        app_res = await client.post(
            "/api/v1/stories/approve",
            json={"story_id": str(story.id)},
        )
        assert app_res.status_code == 200
        app_data = app_res.json()
        assert app_data["status"] == "approved"
        assert app_data["approved_content"] == app_data["working_content"]
        assert any(v["is_approved"] for v in app_data["versions"])

    # Phase D: Creative Direction Adaptive Interview
    intent_adapter = _QueueAdapter(
        [
            {
                "visual_style": "Realistic Cinematic Film",
                "overall_mood": "Tense & Suspenseful",
                "pacing": None,
                "lighting": None,
                "camera_preferences": None,
                "audience_experience": None,
                "ending_tone": None,
                "next_question": "How should the pacing feel as she approaches the cliff edge?",
                "quick_options": ["Urgent & kinetic", "Slow-burn atmospheric"],
                "target_dimension": "pacing",
            },
            {
                "visual_style": "Realistic Cinematic Film",
                "overall_mood": "Tense & Suspenseful",
                "pacing": "Urgent & kinetic",
                "lighting": "Cold desaturated mist",
                "camera_preferences": "Intimate handheld tracking",
                "audience_experience": "Mature Thriller / Drama",
                "ending_tone": "Emotional bittersweet release",
                "next_question": "Creative direction is complete!",
                "quick_options": [],
                "target_dimension": None,
            },
        ]
    )

    with patch("app.api.v1.endpoints.intent.LLMService") as mock_intent_llm:
        mock_intent_llm.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=intent_adapter
        )

        i1 = await client.post(
            "/api/v1/intent/interview",
            json={"project_id": str(project.id), "story_id": str(story.id)},
        )
        assert i1.status_code == 200
        id1 = i1.json()
        assert id1["is_complete"] is False
        assert id1["creative_intent"]["overall_mood"] == "Tense & Suspenseful"
        assert "overall_mood" not in id1["missing_dimensions"]
        assert "pacing" in id1["missing_dimensions"]

        i2 = await client.post(
            "/api/v1/intent/answer",
            json={
                "project_id": str(project.id),
                "answer": "Urgent kinetic pacing, cold misty dusk lighting, intimate handheld tracking, mature thriller ending with bittersweet release.",
            },
        )
        assert i2.status_code == 200
        id2 = i2.json()
        assert id2["is_complete"] is True
        assert id2["missing_dimensions"] == []
        assert id2["creative_intent"]["lighting"] == "Cold desaturated mist"
