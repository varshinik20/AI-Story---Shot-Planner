"""Phase B integration & unit tests: LLMService, DocumentService, unified intake & upload."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from docx import Document as DocxDocument
from httpx import AsyncClient
from reportlab.pdfgen import canvas as pdf_canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models.domain import ModelUsageLog, Story
from app.services.document_service import DocumentService
from app.services.llm_service import LLMCallResult, LLMService


def _build_pdf_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _build_docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    doc = DocxDocument()
    doc.add_paragraph(text)
    doc.save(buf)
    return buf.getvalue()


class _FakeAdapter:
    """Deterministic OpenAI adapter stub returning scripted JSON payloads with token usage."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

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
        self.calls.append({"messages": messages, "model": model, "json_mode": json_mode})
        payload = self._responses.pop(0)
        return LLMCallResult(
            content=json.dumps(payload),
            model="gpt-4o",
            input_tokens=120,
            output_tokens=45,
            execution_time_ms=85,
            estimated_cost_usd=0.00075,
            request_id="req-test-123",
        )


def test_document_service_extracts_txt_docx_and_pdf() -> None:
    svc = DocumentService()

    txt_doc = svc.extract_text(
        filename="cliff.txt",
        content_bytes=b"The girl was running towards the edge of the cliff and fell down.",
    )
    assert txt_doc.file_type == "txt"
    assert "cliff and fell down" in txt_doc.extracted_text

    docx_doc = svc.extract_text(
        filename="story.docx",
        content_bytes=_build_docx_bytes("Maya waited at the lighthouse before dawn."),
    )
    assert docx_doc.file_type == "docx"
    assert "Maya waited at the lighthouse" in docx_doc.extracted_text

    pdf_doc = svc.extract_text(
        filename="script.pdf",
        content_bytes=_build_pdf_bytes("A lone hiker crossed the ridge in fog."),
    )
    assert pdf_doc.file_type == "pdf"
    assert pdf_doc.page_count == 1
    assert "lone hiker" in pdf_doc.extracted_text


@pytest.mark.asyncio
async def test_cliff_fall_intake_preserves_context_without_inventing_title(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Part 4 cliff-fall requirement: capture premise, never invent title, ask naturally."""
    fake_adapter = _FakeAdapter(
        [
            {
                "intent": "story_creation",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": None,
                "extracted_story_context": "The girl was running towards the edge of the cliff and fell down.",
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": (
                    "That's a gripping premise — I have the cliff-fall scene noted! "
                    "What would you like to title your story?"
                ),
            },
            {
                "intent": "provide_details",
                "extracted_story_title": "The Edge of Dawn",
                "explicit_title_provided": True,
                "extracted_visual_style": None,
                "extracted_story_context": None,
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": (
                    'Great title — "The Edge of Dawn". What visual style would you like '
                    "(such as Realistic Cinematic Film, Pixar / Animated, Anime, or Noir)?"
                ),
            },
            {
                "intent": "provide_details",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": "Realistic Cinematic Film",
                "extracted_story_context": None,
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": (
                    'Here is what I have so far: "The Edge of Dawn" in Realistic Cinematic Film style, '
                    "about the girl running toward the cliff edge and falling. Shall I start developing the story?"
                ),
            },
        ]
    )

    with patch("app.api.v1.endpoints.chat.LLMService") as mock_llm_cls:
        def _make_llm(session, settings):
            return LLMService(session=session, settings=settings, adapter=fake_adapter)

        mock_llm_cls.side_effect = _make_llm

        # Turn 1: Typed text cliff-fall request (explicit legacy intake mode)
        r1 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "The girl was running towards the edge of the cliff and fell down. Now create a story.",
                "input_source": "text",
                "auto_pipeline": False,
            },
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["intake_state"]["story_title"] is None
        assert "cliff" in (d1["intake_state"]["story_context"] or "").lower()
        assert "story_title" in d1["missing_fields"]
        assert "visual_style" in d1["missing_fields"]
        assert "The user" not in d1["assistant_message"]
        assert d1["workflow_stage"] == "intake"

        # Turn 2: Voice input supplies title through the exact same pipeline
        r2 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "The Edge of Dawn",
                "input_source": "voice",
                "project_id": d1["project_id"],
                "conversation_id": d1["conversation_id"],
                "auto_pipeline": False,
            },
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["intake_state"]["story_title"] == "The Edge of Dawn"
        assert "story_title" not in d2["missing_fields"]
        assert d2["missing_fields"] == ["visual_style"]
        assert "voice" in d2["intake_state"]["input_sources_seen"]
        assert "cliff" in d2["intake_state"]["story_context"].lower()

        # Turn 3: Visual style supplied -> awaits confirmation
        r3 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Realistic Cinematic Film",
                "input_source": "text",
                "project_id": d1["project_id"],
                "conversation_id": d1["conversation_id"],
                "auto_pipeline": False,
            },
        )
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["missing_fields"] == []
        assert d3["needs_confirmation"] is True
        assert d3["workflow_stage"] == "intake_confirmation"

        # Turn 4: Confirmation fast-path -> unlocks story_ready and creates Story row
        r4 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "Yes, looks good",
                "input_source": "text",
                "project_id": d1["project_id"],
                "conversation_id": d1["conversation_id"],
                "auto_pipeline": False,
            },
        )
        assert r4.status_code == 200
        d4 = r4.json()
        assert d4["ready_for_story_development"] is True
        assert d4["workflow_stage"] == "story_ready"

    logs = (await db_session.execute(select(ModelUsageLog))).scalars().all()
    assert len(logs) == 3
    assert all(log.success and log.input_tokens == 120 and log.output_tokens == 45 for log in logs)

    stories = (await db_session.execute(select(Story))).scalars().all()
    assert len(stories) == 1
    assert stories[0].title == "The Edge of Dawn"
    assert "cliff" in stories[0].original_content.lower()


@pytest.mark.asyncio
async def test_story_upload_docx_and_missing_key_error(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Uploaded DOCX runs through DocumentService + StoryIntakeEngine; missing key returns 503 + logs failure."""
    docx_bytes = _build_docx_bytes("Elena opened the rusted gate at dusk and heard footsteps behind her.")

    fake_adapter = _FakeAdapter(
        [
            {
                "intent": "provide_details",
                "extracted_story_title": None,
                "explicit_title_provided": False,
                "extracted_visual_style": None,
                "extracted_story_context": "Elena opened the rusted gate at dusk and heard footsteps behind her.",
                "is_confirming": False,
                "requests_title_suggestions": False,
                "requests_style_suggestions": False,
                "suggested_titles": [],
                "natural_response": "I've read your story file! What title would you like to give this story?",
            }
        ]
    )

    with patch("app.api.v1.endpoints.stories.LLMService") as mock_llm_cls:
        mock_llm_cls.side_effect = lambda session, settings: LLMService(
            session=session, settings=settings, adapter=fake_adapter
        )
        res = await client.post(
            "/api/v1/stories/upload",
            data={"auto_pipeline": "false"},
            files={
                "file": (
                    "elena.docx",
                    docx_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["filename"] == "elena.docx"
        assert "rusted gate at dusk" in body["extracted_text"]
        assert body["intake_state"]["story_context"] == body["extracted_text"]
        assert "story_title" in body["missing_fields"]

    # Verify missing API key returns structured 503 and logs failed ModelUsageLog
    empty_settings = Settings(
        DATABASE_URL=str(db_session.bind.url),
        OPENAI_API_KEY="",
    )
    llm_missing = LLMService(session=db_session, settings=empty_settings)
    with pytest.raises(Exception) as exc_info:
        await llm_missing.generate_text(
            messages=[{"role": "user", "content": "hi"}],
            engine="story_intake",
            operation="test_missing_key",
        )
    assert getattr(exc_info.value, "status_code", None) == 503
    failed_logs = (
        await db_session.execute(select(ModelUsageLog).where(ModelUsageLog.success.is_(False)))
    ).scalars().all()
    assert len(failed_logs) >= 1
