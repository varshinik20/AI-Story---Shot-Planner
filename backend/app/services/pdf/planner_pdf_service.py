"""ReportLab production Shot Planner PDF generator matching the reference layout."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db.models.domain import (
    Character,
    CreativeIntent,
    Location,
    Scene,
    Shot,
    Story,
)
from app.db.models.project import Project
from app.services.pdf.planner_pdf_layout import (
    ACCENT_GREEN,
    BORDER_GRAY,
    CONTENT_WIDTH,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    PAGE_SIZE,
    SURFACE_ALT,
    TEXT_MUTED,
    build_overview_table,
    build_planner_styles,
    build_shot_table,
    esc_html,
)
from app.services.pdf.planner_pdf_validator import (
    PlannerValidationSummary,
    validate_planner_for_export,
)


def _derive_logline(project: Project, story: Story | None) -> str:
    structure = (story.structure_json or {}) if story else {}
    explicit = str(structure.get("logline") or "").strip()
    if explicit:
        return explicit
    candidate = (story.premise if story else None) or project.description or ""
    if candidate.strip():
        first_sentence = candidate.strip().split("\n")[0].strip()
        if len(first_sentence) > 220:
            return first_sentence[:217].rstrip() + "..."
        return first_sentence
    if story and story.approved_content:
        first_sentence = story.approved_content.strip().split(".")[0].strip()
        if first_sentence:
            return first_sentence + "."
    return "Production shot planner derived from the creator-approved story."


def _derive_creators_intent_rows(
    *,
    story: Story | None,
    intent: CreativeIntent | None,
    characters: list[Character],
) -> list[tuple[str, str]]:
    answers = (intent.interview_answers or {}) if intent else {}
    structure = (story.structure_json or {}) if story else {}

    visual_style = (
        (intent.visual_style if intent else None)
        or (story.visual_style if story else None)
        or "Cinematic Realism"
    )
    atmosphere = (
        answers.get("overall_atmosphere")
        or (intent.overall_mood if intent else None)
        or "Grounded, dramatic atmosphere"
    )
    char_treatment = answers.get("character_treatment") or (
        "; ".join(
            f"{c.name}: {c.emotional_development}"
            for c in characters
            if c.emotional_development
        )
        or "Consistent visual continuity and character-motivated framing"
    )
    emotional_impact = (
        answers.get("intended_emotional_impact")
        or (intent.audience_experience if intent else None)
        or "Engaging audience immersion aligned with creative direction"
    )
    lighting_color = (
        answers.get("lighting_and_color")
        or (intent.lighting if intent else None)
        or "Motivated lighting matched to scene time of day"
    )
    ending_exp = (
        answers.get("desired_ending_experience")
        or (intent.ending_tone if intent else None)
        or "Resonant narrative closure"
    )
    central_theme = (
        answers.get("central_theme")
        or structure.get("central_theme")
        or structure.get("climax")
        or (story.premise if story else None)
        or "Dramatic cause and consequence"
    )

    rows = [
        ("Visual style", str(visual_style)),
        ("Overall atmosphere", str(atmosphere)),
        ("Character treatment", str(char_treatment)),
        ("Intended emotional impact", str(emotional_impact)),
        ("Lighting and colour direction", str(lighting_color)),
        ("Desired ending experience", str(ending_exp)),
        ("Central theme", str(central_theme)),
    ]
    if structure.get("genre"):
        rows.insert(0, ("Genre", str(structure["genre"])))
    return rows


class PlannerPDFService:
    """Builds and validates CINEMIND Shot Planner PDFs following the approved reference specification."""

    def build_planner_pdf(
        self,
        *,
        project: Project,
        story: Story | None,
        intent: CreativeIntent | None,
        characters: list[Character],
        locations: list[Location],
        scenes: list[Scene],
        shots_by_scene: dict[Any, list[Shot]],
        approved_at: datetime | None = None,
        validate: bool = True,
    ) -> bytes:
        summary: PlannerValidationSummary
        if validate:
            summary = validate_planner_for_export(
                project=project,
                story=story,
                intent=intent,
                characters=characters,
                locations=locations,
                scenes=scenes,
                shots_by_scene=shots_by_scene,
            )
        else:
            ordered = sorted(scenes, key=lambda s: s.scene_order)
            all_sh = [sh for sc in ordered for sh in shots_by_scene.get(sc.id, [])]
            summary = PlannerValidationSummary(
                scene_count=len(ordered),
                shot_count=len(all_sh),
                dialogue_lines_count=sum(len(sh.dialogue or []) for sh in all_sh),
                total_runtime_seconds=sum(sh.duration_seconds for sh in all_sh),
                character_count=len(characters),
                location_count=len(locations),
            )

        answers = (intent.interview_answers or {}) if intent else {}
        production_format = str(answers.get("production_format") or "16:9 · 24 FPS")
        ordered_scenes = sorted(scenes, key=lambda s: s.scene_order)
        logline = _derive_logline(project, story)
        styles = build_planner_styles()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=PAGE_SIZE,
            leftMargin=MARGIN_LEFT,
            rightMargin=MARGIN_RIGHT,
            topMargin=MARGIN_TOP,
            bottomMargin=MARGIN_BOTTOM,
            title=f"Shot Planner - {project.title}",
            author="CINEMIND / StoryForge",
        )

        elements: list[Any] = []

        # =====================================================================
        # PAGE 1 — PROJECT OVERVIEW
        # =====================================================================
        elements.append(Paragraph("SHOT PLANNER", styles.eyebrow))
        elements.append(Paragraph(esc_html(project.title), styles.film_title))
        elements.append(Paragraph(esc_html(logline), styles.logline))

        # Five project statistics banner
        dl_label = "1 DIALOGUE LINE" if summary.dialogue_lines_count == 1 else f"{summary.dialogue_lines_count} DIALOGUE LINES"
        sc_label = "1 SCENE" if summary.scene_count == 1 else f"{summary.scene_count} SCENES"
        sh_label = "1 SHOT" if summary.shot_count == 1 else f"{summary.shot_count} SHOTS"
        stats_line = (
            f"{sc_label} | "
            f"{sh_label} | "
            f"{dl_label} | "
            f"{summary.total_runtime_seconds} SECONDS | "
            f"{esc_html(production_format)}"
        )
        stats_box = Table(
            [[Paragraph(stats_line, styles.stat_banner)]],
            colWidths=[CONTENT_WIDTH],
        )
        stats_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SURFACE_ALT),
                    ("BOX", (0, 0), (-1, -1), 0.6, BORDER_GRAY),
                    ("LINEABOVE", (0, 0), (-1, 0), 1.5, ACCENT_GREEN),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(stats_box)
        elements.append(Spacer(1, 8))

        # CREATOR'S INTENT
        elements.append(Paragraph("CREATOR'S INTENT", styles.section_heading))
        intent_rows = [
            [
                Paragraph("DIMENSION", styles.table_header_light),
                Paragraph("CREATIVE DIRECTION", styles.table_header_light),
            ]
        ]
        for label, value in _derive_creators_intent_rows(
            story=story, intent=intent, characters=characters
        ):
            intent_rows.append(
                [
                    Paragraph(esc_html(label), styles.cell_bold),
                    Paragraph(esc_html(value), styles.cell_normal),
                ]
            )
        elements.append(build_overview_table(intent_rows, [185, CONTENT_WIDTH - 185]))

        # CHARACTERS
        elements.append(Paragraph("CHARACTERS", styles.section_heading))
        char_rows = [
            [
                Paragraph("NAME", styles.table_header_light),
                Paragraph("ROLE", styles.table_header_light),
                Paragraph("LOOK", styles.table_header_light),
                Paragraph("PERSONALITY AND VOICE", styles.table_header_light),
            ]
        ]
        for ch in characters:
            role_text = ch.role
            if ch.age_range:
                role_text = f"{role_text}\nAge: {ch.age_range}"
            look_text = ch.physical_appearance
            if ch.clothing:
                look_text = f"{look_text} Clothing: {ch.clothing}"
            pv_text = f"{ch.personality} Voice: {ch.voice_characteristics}"
            char_rows.append(
                [
                    Paragraph(esc_html(ch.name), styles.cell_bold),
                    Paragraph(esc_html(role_text), styles.cell_normal),
                    Paragraph(esc_html(look_text), styles.cell_normal),
                    Paragraph(esc_html(pv_text), styles.cell_normal),
                ]
            )
        elements.append(
            build_overview_table(char_rows, [145, 105, 265, CONTENT_WIDTH - 515])
        )

        # LOCATIONS
        elements.append(Paragraph("LOCATIONS", styles.section_heading))
        loc_rows = [
            [
                Paragraph("LOCATION", styles.table_header_light),
                Paragraph("DESCRIPTION", styles.table_header_light),
            ]
        ]
        for loc in locations:
            desc_parts = [loc.description]
            if loc.environment:
                desc_parts.append(f"Atmosphere: {loc.environment}")
            if loc.time_of_day:
                desc_parts.append(f"Time: {loc.time_of_day}")
            if loc.lighting_characteristics:
                desc_parts.append(f"Lighting: {loc.lighting_characteristics}")
            if loc.visual_elements:
                desc_parts.append(f"Elements: {', '.join(loc.visual_elements)}")
            loc_rows.append(
                [
                    Paragraph(esc_html(loc.name), styles.cell_bold),
                    Paragraph(esc_html(" | ".join(desc_parts)), styles.cell_normal),
                ]
            )
        elements.append(build_overview_table(loc_rows, [185, CONTENT_WIDTH - 185]))

        # =====================================================================
        # SCENE-WISE SHOT PLANNER
        # =====================================================================
        for sc in ordered_scenes:
            elements.append(PageBreak())
            sc_shots = sorted(shots_by_scene.get(sc.id, []), key=lambda x: x.shot_order)
            sc_runtime = sum(sh.duration_seconds for sh in sc_shots)

            header_block = [
                Paragraph(
                    f"{esc_html(project.title.upper())} · SCENE {sc.scene_order}",
                    styles.eyebrow,
                ),
                Paragraph(
                    f"{esc_html(sc.scene_id)} · {esc_html(sc.title)}",
                    styles.scene_heading,
                ),
                Paragraph(
                    f"<b>Location:</b> {esc_html(sc.location)}  |  "
                    f"<b>Time:</b> {esc_html(sc.time_of_day)}  |  "
                    f"<b>Shots:</b> {len(sc_shots)}  |  "
                    f"<b>Duration:</b> {sc_runtime}s",
                    styles.scene_meta,
                ),
                Paragraph(esc_html(sc.summary), styles.scene_summary),
                HRFlowable(width="100%", thickness=0.6, color=BORDER_GRAY, spaceAfter=8),
            ]

            shot_rows: list[list[Any]] = [
                [
                    Paragraph("SHOT", styles.table_header_dark),
                    Paragraph("SEC", styles.table_header_dark),
                    Paragraph("FRAMING · CAMERA", styles.table_header_dark),
                    Paragraph("CHARACTERS · LOCATION", styles.table_header_dark),
                    Paragraph("WHAT WE SEE", styles.table_header_dark),
                    Paragraph("DIALOGUE", styles.table_header_dark),
                    Paragraph("EMOTION", styles.table_header_dark),
                    Paragraph("SOUND", styles.table_header_dark),
                ]
            ]

            for sh in sc_shots:
                cam = sh.camera if isinstance(sh.camera, dict) else {}
                angle = str(cam.get("angle") or "Eye Level")
                movement = str(cam.get("movement") or "Static")
                framing_cam_html = (
                    f"<b>{esc_html(sh.framing)}</b><br/>"
                    f"Angle: {esc_html(angle)}<br/>"
                    f"Move: {esc_html(movement)}"
                )

                chars_str = ", ".join(sh.characters or []) or "None"
                chars_loc_html = f"<b>{esc_html(chars_str)}</b><br/>{esc_html(sh.location)}"

                dialogue_entries = sh.dialogue or []
                if dialogue_entries:
                    formatted_lines = []
                    for d in dialogue_entries:
                        spk = esc_html(d.get("speaker", ""))
                        line = esc_html(d.get("exact_line") or d.get("line") or "")
                        deliv = esc_html(d.get("delivery", ""))
                        if deliv:
                            formatted_lines.append(f'<b>{spk}</b> ({deliv}): "{line}"')
                        else:
                            formatted_lines.append(f'<b>{spk}</b>: "{line}"')
                    dlg_cell = Paragraph("<br/>".join(formatted_lines), styles.cell_normal)
                else:
                    dlg_cell = Paragraph("None", styles.cell_muted)

                shot_rows.append(
                    [
                        Paragraph(esc_html(sh.shot_id), styles.cell_bold),
                        Paragraph(f"{sh.duration_seconds}s", styles.cell_center),
                        Paragraph(framing_cam_html, styles.cell_normal),
                        Paragraph(chars_loc_html, styles.cell_normal),
                        Paragraph(esc_html(sh.visual_description), styles.cell_normal),
                        dlg_cell,
                        Paragraph(esc_html(sh.emotion), styles.cell_normal),
                        Paragraph(esc_html(sh.sound), styles.cell_normal),
                    ]
                )

            # Keep scene header paired smoothly with table start
            elements.append(KeepTogether(header_block))
            elements.append(build_shot_table(shot_rows))

        approved_str = (approved_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")

        def _draw_footer(canvas_obj: Any, doc_obj: Any) -> None:
            canvas_obj.saveState()
            canvas_obj.setFont("Helvetica", 7.5)
            canvas_obj.setFillColor(TEXT_MUTED)
            canvas_obj.drawString(
                MARGIN_LEFT,
                0.28 * inch,
                f"CINEMIND / StoryForge · {project.title} · Approved {approved_str}",
            )
            canvas_obj.drawRightString(
                PAGE_SIZE[0] - MARGIN_RIGHT,
                0.28 * inch,
                f"Page {doc_obj.page}",
            )
            canvas_obj.restoreState()

        doc.build(elements, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
        return buffer.getvalue()
