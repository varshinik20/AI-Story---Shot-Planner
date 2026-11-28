"""Editorial typography, colors, margins, and ReportLab table styles matching the reference PDF."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Table, TableStyle

PAGE_SIZE = landscape(A4)
MARGIN_LEFT = 32
MARGIN_RIGHT = 32
MARGIN_TOP = 38
MARGIN_BOTTOM = 36
CONTENT_WIDTH = PAGE_SIZE[0] - MARGIN_LEFT - MARGIN_RIGHT  # ~777.89 pt

# Palette matching clean editorial Shot Planner aesthetic
ACCENT_GREEN = colors.HexColor("#10A37F")
ACCENT_GREEN_DARK = colors.HexColor("#0D8A6B")
TEXT_DARK = colors.HexColor("#111827")
TEXT_BODY = colors.HexColor("#1F2937")
TEXT_MUTED = colors.HexColor("#6B7280")
BORDER_GRAY = colors.HexColor("#E5E7EB")
BORDER_STRONG = colors.HexColor("#D1D5DB")
HEADER_DARK = colors.HexColor("#1F2937")
SURFACE_SOFT = colors.HexColor("#F3F4F6")
SURFACE_ALT = colors.HexColor("#F9FAFB")
BG_WHITE = colors.white


def esc_html(value: Any) -> str:
    """Escape XML entities for ReportLab Paragraph flowables while preserving line breaks."""
    text = str(value if value is not None else "").strip()
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


@dataclass(slots=True)
class PlannerStyles:
    eyebrow: ParagraphStyle
    film_title: ParagraphStyle
    logline: ParagraphStyle
    stat_banner: ParagraphStyle
    section_heading: ParagraphStyle
    scene_heading: ParagraphStyle
    scene_meta: ParagraphStyle
    scene_summary: ParagraphStyle
    table_header_light: ParagraphStyle
    table_header_dark: ParagraphStyle
    cell_bold: ParagraphStyle
    cell_normal: ParagraphStyle
    cell_muted: ParagraphStyle
    cell_center: ParagraphStyle


def build_planner_styles() -> PlannerStyles:
    base = getSampleStyleSheet()
    return PlannerStyles(
        eyebrow=ParagraphStyle(
            "PlannerEyebrow",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=ACCENT_GREEN_DARK,
            spaceAfter=3,
        ),
        film_title=ParagraphStyle(
            "PlannerFilmTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            textColor=TEXT_DARK,
            spaceAfter=5,
        ),
        logline=ParagraphStyle(
            "PlannerLogline",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13.5,
            textColor=TEXT_MUTED,
            spaceAfter=10,
        ),
        stat_banner=ParagraphStyle(
            "PlannerStatBanner",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=12,
            textColor=TEXT_DARK,
        ),
        section_heading=ParagraphStyle(
            "PlannerSectionHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=TEXT_DARK,
            spaceBefore=11,
            spaceAfter=5,
        ),
        scene_heading=ParagraphStyle(
            "PlannerSceneHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=TEXT_DARK,
            spaceAfter=3,
        ),
        scene_meta=ParagraphStyle(
            "PlannerSceneMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12.5,
            textColor=TEXT_MUTED,
            spaceAfter=5,
        ),
        scene_summary=ParagraphStyle(
            "PlannerSceneSummary",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12,
            textColor=TEXT_BODY,
            spaceAfter=8,
        ),
        table_header_light=ParagraphStyle(
            "PlannerHeaderLight",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=TEXT_DARK,
        ),
        table_header_dark=ParagraphStyle(
            "PlannerHeaderDark",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
        ),
        cell_bold=ParagraphStyle(
            "PlannerCellBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=TEXT_DARK,
        ),
        cell_normal=ParagraphStyle(
            "PlannerCellNormal",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=TEXT_BODY,
        ),
        cell_muted=ParagraphStyle(
            "PlannerCellMuted",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10.5,
            textColor=TEXT_MUTED,
        ),
        cell_center=ParagraphStyle(
            "PlannerCellCenter",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10.5,
            textColor=TEXT_DARK,
            alignment=1,
        ),
    )


def build_overview_table(rows: list[list[Any]], col_widths: list[float]) -> Table:
    table = Table(rows, colWidths=col_widths, repeatRows=1, splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SURFACE_SOFT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_WHITE, SURFACE_ALT]),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
                ("LINEBELOW", (0, 0), (-1, 0), 0.9, BORDER_STRONG),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


# Exact 8-column widths summing to 777 pt inside landscape(A4) 32pt margins
SHOT_TABLE_COL_WIDTHS = [56, 32, 92, 108, 187, 143, 72, 87]


def build_shot_table(rows: list[list[Any]]) -> Table:
    table = Table(rows, colWidths=SHOT_TABLE_COL_WIDTHS, repeatRows=1, splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_WHITE, SURFACE_ALT]),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
                ("LINEBELOW", (0, 0), (-1, 0), 1.0, ACCENT_GREEN),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table
