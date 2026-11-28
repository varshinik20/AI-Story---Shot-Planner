"""Phase I tests: Final Approval Gate, ReportLab PDF Export & Usage Telemetry."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.domain import (
    Character,
    CreativeIntent,
    Location,
    ModelUsageLog,
    Scene,
    Shot,
    Story,
)
from app.db.models.project import Project


@pytest.mark.asyncio
async def test_planner_approval_gate_pdf_export_and_usage_telemetry(
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
        working_content="Elena sprinted toward the cliff edge and fell down, catching a gnarled root.",
        approved_content="Elena sprinted toward the cliff edge and fell down, catching a gnarled root.",
        status="approved",
    )
    intent = CreativeIntent(
        project_id=project.id,
        visual_style="Realistic Cinematic Film",
        overall_mood="Tense & Suspenseful",
        pacing="Urgent",
        lighting="Cold desaturated mist",
        camera_preferences="Handheld tracking",
        audience_experience="Mature Thriller",
        ending_tone="Hopeful survival",
        is_complete=True,
    )
    ch = Character(
        project_id=project.id,
        character_code="CHAR-001",
        name="Elena",
        role="Protagonist",
        physical_appearance="Determined young woman in windbreaker",
        personality="Resilient",
        voice_characteristics="Quiet gasps",
    )
    loc = Location(
        project_id=project.id,
        location_code="LOC-001",
        name="Coastal Cliff Ridge",
        description="Wet slate cliff edge over foggy sea gorge",
        time_of_day="Dawn",
        lighting_characteristics="Pale blue morning fog",
        visual_elements=["Wet slate", "Twisted root"],
    )
    scene = Scene(
        project_id=project.id,
        scene_id="S01",
        scene_order=1,
        title="Run & Cliff Plunge",
        location="Coastal Cliff Ridge",
        time_of_day="Dawn",
        summary="Elena runs to the cliff edge and plunges down.",
        event_ids=["E001", "E002"],
        is_approved=True,
        shots_generated=True,
    )
    db_session.add_all([story, intent, ch, loc, scene])
    await db_session.flush()

    shot = Shot(
        project_id=project.id,
        scene_uuid=scene.id,
        shot_id="S01_SH01",
        shot_order=1,
        duration_seconds=5,
        framing="Wide Tracking Shot",
        camera={"angle": "Eye Level", "movement": "Handheld Tracking"},
        characters=["Elena"],
        location="Coastal Cliff Ridge",
        visual_description="Elena sprints through dense sea mist toward the cliff edge.",
        dialogue=[],
        emotion="terror",
        sound="Racing heartbeat and crumbling gravel",
    )
    usage = ModelUsageLog(
        project_id=project.id,
        request_id="req-usage-1",
        engine="production",
        operation="generate_scene_shots",
        model="gpt-4o",
        input_tokens=450,
        output_tokens=280,
        estimated_cost_usd=0.003925,
        execution_time_ms=1250,
        scene_id="SC-001",
        success=True,
    )
    db_session.add_all([shot, usage])
    await db_session.commit()

    # 1. Exporting BEFORE creator approval must fail with 409 Conflict
    unapproved_pdf = await client.get(f"/api/v1/planner/export/{project.id}")
    assert unapproved_pdf.status_code == 409

    # 2. Approve final shot plan
    approve_res = await client.post(
        "/api/v1/planner/approve",
        json={"project_id": str(project.id), "notes": "Approved for production shoot."},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["approved"] is True

    # 3. Export real ReportLab PDF & verify readable content via pypdf
    pdf_res = await client.get(f"/api/v1/planner/export/{project.id}")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(pdf_res.content))
    full_pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "The Edge of Dawn" in full_pdf_text
    assert "Elena" in full_pdf_text
    assert "Coastal Cliff Ridge" in full_pdf_text
    assert "S01_SH01" in full_pdf_text
    assert "None" in full_pdf_text
    assert "1 SCENE | 1 SHOT | 0 DIALOGUE LINES | 5 SECONDS" in full_pdf_text

    # 4. Verify usage reporting endpoint returns exact token & cost telemetry
    usage_res = await client.get(f"/api/v1/usage/{project.id}")
    assert usage_res.status_code == 200
    u_data = usage_res.json()
    assert u_data["total_calls"] == 1
    assert u_data["total_input_tokens"] == 450
    assert u_data["total_output_tokens"] == 280
    assert u_data["total_estimated_cost_usd"] == 0.003925

    # 5. Verify workspace hydration endpoint returns complete project state
    ws_res = await client.get(f"/api/v1/planner/{project.id}")
    assert ws_res.status_code == 200
    assert ws_res.json()["final_approved"] is True
    assert len(ws_res.json()["scenes"]) == 1
