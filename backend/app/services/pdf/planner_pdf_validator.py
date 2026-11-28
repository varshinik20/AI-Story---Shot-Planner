"""Pre-export validation enforcing completeness, accuracy, and dialogue grounding."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import status

from app.core.exceptions import CineMindException
from app.db.models.domain import (
    Character,
    CreativeIntent,
    Location,
    Scene,
    Shot,
    Story,
)
from app.db.models.project import Project


class PDFValidationError(CineMindException):
    """Raised when a shot planner fails pre-export validation checks."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        joined = "; ".join(issues[:6])
        if len(issues) > 6:
            joined += f" (+{len(issues) - 6} more)"
        super().__init__(
            message=f"Shot Planner PDF validation failed: {joined}",
            code="PDF_VALIDATION_FAILED",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


@dataclass(slots=True)
class PlannerValidationSummary:
    """Verified quantitative counts computed strictly from persisted database rows."""

    scene_count: int
    shot_count: int
    dialogue_lines_count: int
    total_runtime_seconds: int
    character_count: int
    location_count: int


def _norm_text(value: str) -> str:
    cleaned = (
        value.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2014", "--")
    )
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _character_exists(ref_name: str, known_names: list[str]) -> bool:
    ref_norm = _norm_text(ref_name)
    if not ref_norm:
        return False
    for known in known_names:
        known_norm = _norm_text(known)
        if ref_norm == known_norm or ref_norm in known_norm or known_norm in ref_norm:
            return True
    return False


def _location_exists(loc_name: str, known_locations: list[str]) -> bool:
    loc_norm = _norm_text(loc_name)
    if not loc_norm:
        return False
    for known in known_locations:
        known_norm = _norm_text(known)
        if loc_norm == known_norm or loc_norm in known_norm or known_norm in loc_norm:
            return True
    return False


def _dialogue_grounded_in_story(line: str, approved_story_norm: str) -> bool:
    if not approved_story_norm:
        return True
    line_norm = _norm_text(line).strip("\"'")
    if not line_norm:
        return False
    if line_norm in approved_story_norm:
        return True
    # Also tolerate minor trailing punctuation differences
    stripped_punct = re.sub(r"[.!?,;:]+$", "", line_norm).strip()
    return bool(stripped_punct) and stripped_punct in approved_story_norm


def validate_planner_for_export(
    *,
    project: Project,
    story: Story | None,
    intent: CreativeIntent | None,
    characters: list[Character],
    locations: list[Location],
    scenes: list[Scene],
    shots_by_scene: dict[uuid.UUID, list[Shot]],
) -> PlannerValidationSummary:
    """Validate all structural, continuity, entity, and dialogue constraints before rendering PDF."""
    issues: list[str] = []

    if not project.title or not project.title.strip():
        issues.append("Overview missing project title.")

    if story is None:
        issues.append("Overview missing approved story record.")
    else:
        has_text = bool((story.approved_content or story.working_content or story.premise or "").strip())
        if not has_text:
            issues.append("Story content and logline are empty.")

    if intent is None:
        issues.append("Creator's Intent record is missing.")

    if not characters:
        issues.append("At least one extracted Character is required before PDF export.")

    if not locations:
        issues.append("At least one extracted Location is required before PDF export.")

    if not scenes:
        issues.append("At least one Scene is required before PDF export.")

    known_char_names = [c.name for c in characters if c.name]
    known_loc_names = [loc.name for loc in locations if loc.name]

    approved_story_norm = _norm_text(
        (story.approved_content or story.working_content or "") if story else ""
    )

    seen_shot_ids: set[str] = set()
    total_shots = 0
    total_dialogue_lines = 0
    total_runtime = 0

    ordered_scenes = sorted(scenes, key=lambda s: s.scene_order)
    for sc in ordered_scenes:
        sc_shots = sorted(shots_by_scene.get(sc.id, []), key=lambda x: x.shot_order)
        if not sc_shots:
            issues.append(f"Scene {sc.scene_id} ({sc.title}) has no shots.")
            continue

        if known_loc_names and not _location_exists(sc.location or "", known_loc_names):
            for part_loc in [p.strip() for p in (sc.location or "").split(",") if p.strip()]:
                if not _location_exists(part_loc, known_loc_names):
                    issues.append(
                        f"Scene {sc.scene_id} references unknown location '{part_loc}' not present in Locations table."
                    )

        for sh in sc_shots:
            total_shots += 1
            sid = (sh.shot_id or "").strip()
            if not sid:
                issues.append(f"Scene {sc.scene_id} contains a shot with an empty shot_id.")
            elif sid in seen_shot_ids:
                issues.append(f"Duplicate shot_id detected: '{sid}'.")
            else:
                seen_shot_ids.add(sid)

            if not isinstance(sh.duration_seconds, int) or sh.duration_seconds <= 0:
                issues.append(f"Shot {sid or '?'} has non-positive duration ({sh.duration_seconds}).")
            else:
                total_runtime += sh.duration_seconds

            if not (sh.framing or "").strip():
                issues.append(f"Shot {sid} is missing framing.")

            cam: dict[str, Any] = sh.camera if isinstance(sh.camera, dict) else {}
            angle = str(cam.get("angle") or "").strip()
            movement = str(cam.get("movement") or "").strip()
            if not angle or not movement:
                issues.append(f"Shot {sid} must specify both camera.angle and camera.movement.")

            if not (sh.location or "").strip():
                issues.append(f"Shot {sid} is missing location.")
            elif known_loc_names and not _location_exists(sh.location, known_loc_names):
                issues.append(
                    f"Shot {sid} references unknown location '{sh.location}' not found in Locations table."
                )

            if not (sh.visual_description or "").strip():
                issues.append(f"Shot {sid} is missing visual_description (WHAT WE SEE).")

            if not (sh.emotion or "").strip():
                issues.append(f"Shot {sid} is missing emotion.")

            if not (sh.sound or "").strip():
                issues.append(f"Shot {sid} is missing sound specification.")

            for char_ref in sh.characters or []:
                if known_char_names and not _character_exists(char_ref, known_char_names):
                    issues.append(
                        f"Shot {sid} references character '{char_ref}' not found in Characters table."
                    )

            for d_entry in sh.dialogue or []:
                if not isinstance(d_entry, dict):
                    issues.append(f"Shot {sid} contains malformed dialogue entry.")
                    continue
                speaker = str(d_entry.get("speaker") or "").strip()
                exact_line = str(d_entry.get("exact_line") or d_entry.get("line") or "").strip()
                delivery = str(d_entry.get("delivery") or "").strip()
                if not speaker or not exact_line or not delivery:
                    issues.append(
                        f"Shot {sid} dialogue line must include speaker, exact_line, and delivery."
                    )
                    continue
                if story and story.approved_content and not _dialogue_grounded_in_story(
                    exact_line, approved_story_norm
                ):
                    issues.append(
                        f"Shot {sid} dialogue line \"{exact_line}\" does not match the creator-approved story."
                    )
                total_dialogue_lines += 1

    if total_runtime <= 0 and total_shots > 0:
        issues.append("Calculated total runtime must be positive.")

    if issues:
        raise PDFValidationError(issues)

    return PlannerValidationSummary(
        scene_count=len(ordered_scenes),
        shot_count=total_shots,
        dialogue_lines_count=total_dialogue_lines,
        total_runtime_seconds=total_runtime,
        character_count=len(characters),
        location_count=len(locations),
    )
