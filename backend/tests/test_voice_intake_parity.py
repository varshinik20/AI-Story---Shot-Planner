"""Voice & Adaptive Story Intake Parity Tests (Parts 3, 4, 5, 9, 10, 11, 12, 14)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.domain import Story
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
            input_tokens=180,
            output_tokens=90,
            execution_time_ms=65,
            estimated_cost_usd=0.00135,
            request_id="req-voice-parity",
        )


@pytest.mark.asyncio
async def test_mixed_voice_and_text_intake_regression_and_reload_persistence(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Part 3 + Voice Scenarios 6/7/8 + Part 11/12/14: mixed voice/text converges on same state, confirmation gate, reload."""
    adapter = _QueueAdapter(
        [
            # Turn 1 (voice): "Tell me a story." -> internal leak triggers natural fallback!
            {
                "intent": "story_creation",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": None,
                "extracted_story_context": None,
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "The user wants a story without giving story_title.",
            },
            # Turn 2 (text): "The Shadow Within."
            {
                "intent": "provide_details",
                "extracted_story_title": "The Shadow Within",
                "explicit_title_provided": True,
                "extracted_visual_style": None,
                "extracted_story_context": None,
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "That's an intriguing title! What kind of visual world are you imagining for it?",
            },
            # Turn 3 (voice): "Dark fantasy."
            {
                "intent": "provide_details",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": "Dark fantasy",
                "extracted_story_context": None,
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "Love that direction! What's happening in The Shadow Within?",
            },
            # Turn 4 (voice with pause): "A girl discovers that her shadow is alive."
            {
                "intent": "provide_details",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": None,
                "extracted_story_context": "A girl discovers that her shadow is alive.",
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "So we're creating The Shadow Within with a dark fantasy style about a girl whose shadow is alive. Shall we start building the story?",
            },
            # Turn 5 (voice correction): "Actually, make the style hand-painted animation."
            {
                "intent": "edit_details",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": "Hand-painted animation",
                "extracted_story_context": None,
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "Updated to hand-painted animation while keeping The Shadow Within and your story premise. Ready to begin?",
            },
            # Turn 7 (duplicate confirmation): "Yes" after fast-path confirmation on Turn 6
            {
                "intent": "confirm_intake",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": None,
                "extracted_story_context": None,
                "is_confirming": True,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "Your story workspace for The Shadow Within is already confirmed and ready.",
            },
        ]
    )

    with patch("app.api.v1.endpoints.chat.LLMService") as mock_llm_cls:
        mock_llm_cls.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=adapter
        )

        # Turn 1 (Voice): missing all 3 fields; leaked assistant text replaced cleanly by natural fallback
        r1 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Tell me a story.", "input_source": "voice"},
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert "The user" not in d1["assistant_message"]
        assert "story_title" not in d1["assistant_message"]
        assert "name in mind" in d1["assistant_message"]
        assert d1["intake_state"]["current_stage"] == "awaiting_title"
        assert d1["ready_for_story_development"] is False

        pid = d1["project_id"]
        cid = d1["conversation_id"]

        # Turn 2 (Typed)
        r2 = await client.post(
            "/api/v1/chat/message",
            json={"message": "The Shadow Within.", "input_source": "text", "project_id": pid, "conversation_id": cid},
        )
        d2 = r2.json()
        assert d2["intake_state"]["story_title"] == "The Shadow Within"
        assert d2["missing_fields"] == ["visual_style", "story_context"]

        # Turn 3 (Voice)
        r3 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Dark fantasy.", "input_source": "voice", "project_id": pid, "conversation_id": cid},
        )
        d3 = r3.json()
        assert d3["intake_state"]["visual_style"] == "Dark fantasy"
        assert d3["missing_fields"] == ["story_context"]

        # Turn 4 (Voice): all fields now gathered, confirmation gate MUST block automatic generation
        r4 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "A girl discovers that her shadow is alive.",
                "input_source": "voice",
                "project_id": pid,
                "conversation_id": cid,
            },
        )
        d4 = r4.json()
        assert d4["missing_fields"] == []
        assert d4["needs_confirmation"] is True
        assert d4["ready_for_story_development"] is False
        assert d4["intake_state"]["confirmation_status"] == "not_confirmed"

        # Turn 5 (Voice correction): preserves title & context, updates visual style only
        r5 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Actually, make the style hand-painted animation.",
                "input_source": "voice",
                "project_id": pid,
                "conversation_id": cid,
            },
        )
        d5 = r5.json()
        assert d5["intake_state"]["story_title"] == "The Shadow Within"
        assert d5["intake_state"]["visual_style"] == "Hand-painted animation"
        assert "shadow is alive" in d5["intake_state"]["story_context"]
        assert d5["needs_confirmation"] is True

        # Turn 6 (Confirmation phrase "Let's start.") -> creates single Story row & returns story_id
        r6 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Let's start.", "input_source": "text", "project_id": pid, "conversation_id": cid},
        )
        assert r6.status_code == 200
        d6 = r6.json()
        assert d6["ready_for_story_development"] is True
        assert d6["story_id"] is not None
        assert d6["intake_state"]["confirmation_status"] == "confirmed"
        assert "voice" in d6["intake_state"]["input_sources_seen"]
        assert "text" in d6["intake_state"]["input_sources_seen"]

        # Duplicate confirmation does NOT create duplicate Story row
        r7 = await client.post(
            "/api/v1/chat/message",
            json={"message": "Yes", "input_source": "text", "project_id": pid, "conversation_id": cid},
        )
        assert r7.status_code == 200
        assert r7.json()["story_id"] == d6["story_id"]

    stories = (await db_session.execute(select(Story))).scalars().all()
    assert len(stories) == 1

    # Reload / restore endpoint returns messages and intake state cleanly
    restore_res = await client.get(f"/api/v1/chat/conversations/{cid}")
    assert restore_res.status_code == 200
    restored = restore_res.json()
    assert restored["story_id"] == d6["story_id"]
    assert restored["intake_state"]["visual_style"] == "Hand-painted animation"
    assert len(restored["messages"]) == 14  # 7 user turns + 7 assistant responses


@pytest.mark.asyncio
async def test_legacy_intake_analyze_returns_separated_analysis_and_conversation(
    client: AsyncClient,
) -> None:
    """Part 5 & 14: /api/v1/ai/intake/analyze delegates to StoryIntakeEngine with strict separation."""
    adapter = _QueueAdapter(
        [
            {
                "intent": "story_creation",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": "Anime",
                "extracted_story_context": None,
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "Anime is a great choice! What would you like to name your story?",
            }
        ]
    )

    with patch("app.api.v1.endpoints.ai_chat.LLMService") as mock_llm_cls:
        mock_llm_cls.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=adapter
        )
        res = await client.post(
            "/api/v1/ai/intake/analyze",
            json={"message": "I want an anime story.", "input_source": "voice"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["analysis"]["input_source"] == "voice"
        assert body["analysis"]["extracted_fields"]["visual_style"]["value"] == "Anime"
        assert "story_title" in body["analysis"]["missing_fields"]
        assert body["conversation"]["assistant_message"] == "Anime is a great choice! What would you like to name your story?"
