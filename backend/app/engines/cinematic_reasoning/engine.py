"""Hybrid Cinematography Reasoning Engine: LLM candidate generation + weighted deterministic scoring."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.services.llm_service import LLMService


class ShotTreatmentCandidate(BaseModel):
    label: str
    framing: str
    camera_angle: str
    camera_movement: str
    duration_seconds: int = Field(..., ge=2, le=30)
    lighting_note: str
    rationale: str


class LLMCandidateTreatmentsPayload(BaseModel):
    candidates: list[ShotTreatmentCandidate] = Field(..., min_length=2, max_length=4)


class ScoredTreatment(BaseModel):
    candidate: ShotTreatmentCandidate
    emotion_score: float
    narrative_score: float
    director_score: float
    continuity_score: float
    weighted_total: float
    validation_notes: list[str] = Field(default_factory=list)


class ReasoningDecision(BaseModel):
    selected: ScoredTreatment
    alternatives: list[ScoredTreatment]
    weights: dict[str, float]
    summary_rationale: str


REASONING_SYSTEM_PROMPT = """You are CINEMIND's Cinematography Director.
Given a narrative beat, emotional intensity, creative direction preferences, and previous shot state, propose 3 distinct candidate camera/shot treatments (labeled Option A, Option B, Option C).

Each candidate must choose realistic film grammar:
- framing: e.g., Establishing Wide Shot, Wide Tracking Shot, Medium Shot, Medium Close-Up, Close-Up, Extreme Close-Up, Over-the-Shoulder
- camera_angle: e.g., Eye Level, Low Angle, High Angle, Dutch Angle, Overhead Bird's Eye
- camera_movement: e.g., Static, Handheld Tracking, Dolly Push-In, Whip Pan, Steadicam Follow, Crane Tilt-Down
- duration_seconds: integer 2..15 matching pacing urgency
- lighting_note: concrete lighting cue aligned with creative intent
- rationale: concise cinematic reasoning explaining emotional impact

Return strict JSON matching the schema."""


class CinematicReasoningEngine:
    """Combines LLM visual grammar proposals with deterministic scoring formula:
    Score = w_E * E + w_N * N + w_D * D + w_C * C.
    """

    def __init__(self, settings: Settings, llm_service: LLMService) -> None:
        self.settings = settings
        self.llm = llm_service
        self.weights = {
            "emotion": settings.SCORING_WEIGHT_EMOTION,
            "narrative": settings.SCORING_WEIGHT_NARRATIVE,
            "director": settings.SCORING_WEIGHT_DIRECTOR,
            "continuity": settings.SCORING_WEIGHT_CONTINUITY,
        }

    def score_candidate(
        self,
        candidate: ShotTreatmentCandidate,
        *,
        emotion: str,
        intensity: float,
        narrative_role: str,
        creative_intent: dict[str, Any],
        previous_shot: dict[str, Any] | None = None,
    ) -> ScoredTreatment:
        notes: list[str] = []
        framing_l = candidate.framing.lower()
        angle_l = candidate.camera_angle.lower()
        move_l = candidate.camera_movement.lower()

        # E: Emotion Alignment (0..1)
        e_score = 0.65
        if intensity >= 0.7:
            if any(k in framing_l for k in ("close-up", "medium close", "extreme close")):
                e_score += 0.25
            if any(k in move_l for k in ("handheld", "push", "track", "dolly", "whip")):
                e_score += 0.10
            if candidate.duration_seconds <= 6:
                e_score += 0.05
            elif candidate.duration_seconds > 12:
                e_score -= 0.15
                notes.append("Long duration softens high-intensity urgency.")
        elif intensity <= 0.4:
            if any(k in framing_l for k in ("wide", "establishing", "medium")):
                e_score += 0.25
            if any(k in move_l for k in ("static", "slow", "pan", "steadicam")):
                e_score += 0.10
        else:
            if "medium" in framing_l or "over-the-shoulder" in framing_l:
                e_score += 0.20

        # N: Narrative Role Alignment (0..1)
        role_l = narrative_role.lower()
        n_score = 0.65
        if "climax" in role_l or "crisis" in role_l:
            if any(k in angle_l for k in ("high", "low", "dutch", "overhead")) or "close" in framing_l:
                n_score += 0.25
            if "static" not in move_l:
                n_score += 0.10
        elif "setup" in role_l or "opening" in role_l or "inciting" in role_l:
            if any(k in framing_l for k in ("wide", "establishing", "tracking", "medium")):
                n_score += 0.25
        elif "resolution" in role_l or "ending" in role_l:
            if any(k in move_l for k in ("pull", "tilt", "static", "crane", "slow")) or any(
                k in framing_l for k in ("wide", "close")
            ):
                n_score += 0.25

        # D: Director Intent Fit (0..1)
        d_score = 0.60
        cam_pref = str(creative_intent.get("camera_preferences") or "").lower()
        pacing_pref = str(creative_intent.get("pacing") or "").lower()
        lighting_pref = str(creative_intent.get("lighting") or "").lower()
        if cam_pref and any(tok in move_l or tok in framing_l for tok in cam_pref.split() if len(tok) > 3):
            d_score += 0.25
        if pacing_pref:
            if any(k in pacing_pref for k in ("urgent", "fast", "kinetic")) and candidate.duration_seconds <= 6:
                d_score += 0.15
            elif any(k in pacing_pref for k in ("slow", "contemplative", "measured")) and candidate.duration_seconds >= 5:
                d_score += 0.15
        if lighting_pref and any(tok in candidate.lighting_note.lower() for tok in lighting_pref.split() if len(tok) > 3):
            d_score += 0.10

        # C: Continuity & Grammar Fit (0..1)
        c_score = 0.85
        if previous_shot:
            prev_framing = str(previous_shot.get("framing") or "").lower()
            prev_angle = str(previous_shot.get("camera", {}).get("angle") or "").lower()
            if prev_framing == framing_l and prev_angle == angle_l:
                c_score -= 0.30
                notes.append("Same framing and angle back-to-back risks visual jump cut.")
            elif prev_framing != framing_l:
                c_score += 0.15

        e_clamped = min(1.0, max(0.0, round(e_score, 3)))
        n_clamped = min(1.0, max(0.0, round(n_score, 3)))
        d_clamped = min(1.0, max(0.0, round(d_score, 3)))
        c_clamped = min(1.0, max(0.0, round(c_score, 3)))

        total = round(
            self.weights["emotion"] * e_clamped
            + self.weights["narrative"] * n_clamped
            + self.weights["director"] * d_clamped
            + self.weights["continuity"] * c_clamped,
            4,
        )

        return ScoredTreatment(
            candidate=candidate,
            emotion_score=e_clamped,
            narrative_score=n_clamped,
            director_score=d_clamped,
            continuity_score=c_clamped,
            weighted_total=total,
            validation_notes=notes,
        )

    async def recommend_treatment(
        self,
        *,
        project_id: uuid.UUID,
        beat_description: str,
        emotion: str,
        intensity: float,
        narrative_role: str,
        creative_intent: dict[str, Any],
        previous_shot: dict[str, Any] | None = None,
    ) -> ReasoningDecision:
        prompt = (
            f"Narrative Beat: {beat_description}\n"
            f"Narrative Role: {narrative_role}\n"
            f"Emotion & Intensity: {emotion} ({intensity:.2f})\n"
            f"Creative Intent: {creative_intent}\n"
            f"Previous Shot State: {previous_shot or 'Opening shot of sequence'}\n\n"
            "Propose 3 distinct visual shot treatment candidates (Option A, Option B, Option C)."
        )
        payload, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMCandidateTreatmentsPayload,
            engine="cinematic_reasoning",
            operation="recommend_treatment",
            project_id=project_id,
            temperature=0.45,
            max_tokens=1100,
        )

        scored = [
            self.score_candidate(
                c,
                emotion=emotion,
                intensity=intensity,
                narrative_role=narrative_role,
                creative_intent=creative_intent,
                previous_shot=previous_shot,
            )
            for c in payload.candidates
        ]
        scored.sort(key=lambda s: s.weighted_total, reverse=True)
        selected = scored[0]
        summary_rationale = (
            f"Selected '{selected.candidate.label}' ({selected.candidate.framing}, "
            f"{selected.candidate.camera_angle}, {selected.candidate.camera_movement}) "
            f"with composite score {selected.weighted_total:.3f} "
            f"[E={selected.emotion_score:.2f}, N={selected.narrative_score:.2f}, "
            f"D={selected.director_score:.2f}, C={selected.continuity_score:.2f}]: "
            f"{selected.candidate.rationale}"
        )

        return ReasoningDecision(
            selected=selected,
            alternatives=scored,
            weights=self.weights,
            summary_rationale=summary_rationale,
        )
