"""Audience Experience & Production Feasibility validation engine."""

from __future__ import annotations

from typing import Any

from app.db.models.domain import CreativeIntent, Scene, Shot


class AudienceFeasibilityEngine:
    """Checks audience age/tone alignment and real-world shot production feasibility."""

    def validate(
        self,
        *,
        intent: CreativeIntent | None,
        scenes: list[Scene],
        shots_by_scene: dict[str, list[Shot]],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        audience = ((intent.audience_experience if intent else None) or "").lower()
        ending_tone = ((intent.ending_tone if intent else None) or "").lower()

        is_child_audience = any(k in audience for k in ("child", "kid", "toddler", "preschool"))
        all_shots: list[tuple[Scene, Shot]] = []
        for sc in sorted(scenes, key=lambda s: s.scene_order):
            for sh in sorted(shots_by_scene.get(sc.id, []), key=lambda x: x.shot_order):
                all_shots.append((sc, sh))

                # Production feasibility checks
                if sh.duration_seconds > 20:
                    issues.append(
                        {
                            "category": "feasibility",
                            "severity": "warning",
                            "scene_id": sc.scene_id,
                            "shot_id": sh.shot_id,
                            "message": (
                                f"Shot {sh.shot_id} runs {sh.duration_seconds}s as a single take, "
                                "which risks pacing drag and complex choreographed focus pulls."
                            ),
                            "suggested_fix": "Split long take into 2 shorter shots or trim duration under 15s.",
                        }
                    )
                move_l = ((sh.camera or {}).get("movement") or "").lower()
                angle_l = ((sh.camera or {}).get("angle") or "").lower()
                if "crane" in move_l and sh.duration_seconds < 3:
                    issues.append(
                        {
                            "category": "feasibility",
                            "severity": "warning",
                            "scene_id": sc.scene_id,
                            "shot_id": sh.shot_id,
                            "message": (
                                f"Shot {sh.shot_id} pairs a heavy Crane movement with a {sh.duration_seconds}s cut, "
                                "which may be mechanically abrupt to execute cleanly."
                            ),
                            "suggested_fix": "Extend duration to 4-6s or switch to Steadicam/handheld.",
                        }
                    )

                # Audience mismatch checks
                if is_child_audience:
                    desc_l = f"{sh.visual_description} {sh.emotion} {sh.sound}".lower()
                    if any(w in desc_l for w in ("gore", "blood", "terrifying", "brutal", "graphic", "fatal")):
                        issues.append(
                            {
                                "category": "audience_experience",
                                "severity": "warning",
                                "scene_id": sc.scene_id,
                                "shot_id": sh.shot_id,
                                "message": (
                                    f"Shot {sh.shot_id} contains intense/graphic cues that may distress the stated "
                                    f"target audience ({intent.audience_experience})."
                                ),
                                "suggested_fix": "Soften framing to stylized/suggestive angles or adjust target audience.",
                            }
                        )

        # Ending tone alignment on final shot
        if all_shots and ending_tone:
            last_sc, last_sh = all_shots[-1]
            if any(k in ending_tone for k in ("hopeful", "warm", "triumph", "uplifting")) and last_sh.emotion.lower() in (
                "despair",
                "terror",
                "dread",
            ):
                issues.append(
                    {
                        "category": "audience_experience",
                        "severity": "info",
                        "scene_id": last_sc.scene_id,
                        "shot_id": last_sh.shot_id,
                        "message": (
                            f"Final shot emotion '{last_sh.emotion}' contrasts with stated ending tone '{intent.ending_tone}'."
                        ),
                        "suggested_fix": "Add a final resolution beat or revise ending shot emotion via What-If.",
                    }
                )

        return issues
