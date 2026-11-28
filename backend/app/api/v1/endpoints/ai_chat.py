"""
AI Chat endpoint — routes user messages to OpenAI and returns
structured JSON that the frontend can render as chat messages + shot plans.
"""

import asyncio
import base64
import io
import json
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from typing import Any

from fastapi import APIRouter, HTTPException, status
import httpx
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger("cinemind.ai_chat")
router = APIRouter(prefix="/ai", tags=["AI"])


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _extract_json(raw: str) -> dict[str, Any]:
    """Parse JSON from model output, tolerating markdown fences, prose, and trailing commas."""
    raw = raw.strip()

    def _try_parse(text: str) -> dict[str, Any] | None:
        for candidate in (text, re.sub(r",\s*([}\]])", r"\1", text)):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return None

    direct = _try_parse(raw)
    if direct is not None:
        return direct

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", raw)
    if fenced:
        parsed = _try_parse(fenced.group(1))
        if parsed is not None:
            return parsed

    brace_match = re.search(r"\{[\s\S]*\}", raw)
    if brace_match:
        parsed = _try_parse(brace_match.group(0))
        if parsed is not None:
            return parsed

    raise ValueError(f"No valid JSON found in model output: {raw[:300]}")


def _normalize_options(raw_options: Any) -> list[dict[str, str]] | None:
    """Coerce model-returned options into list[dict[str, str]] | None."""
    if not isinstance(raw_options, list) or not raw_options:
        return None
    normalized: list[dict[str, str]] = []
    for idx, item in enumerate(raw_options, start=1):
        if isinstance(item, str) and item.strip():
            normalized.append({"id": f"opt{idx}", "label": item.strip(), "action": "send"})
        elif isinstance(item, dict) and item.get("label"):
            normalized.append(
                {
                    "id": str(item.get("id") or f"opt{idx}"),
                    "label": str(item["label"]),
                    "action": str(item.get("action") or "send"),
                }
            )
    return normalized or None


_ATMOSPHERE_PREFIX_RE = re.compile(
    r"^(?:in the background|behind (?:him|her|them|it)|around (?:him|her|them|it)|"
    r"overhead|above|below|sunlight|moonlight|shadows|soft |cold |warm |golden |"
    r"desaturated |pale |dim |bright |the lighting|the atmosphere|the air|the sky|"
    r"dust motes|rain |mist |fog |wind )",
    re.IGNORECASE,
)

_META_NOTE_RE = re.compile(
    r"(?:^(?:after a cut to [^,]+,\s*|cut (?:ahead )?to\s+|return to [^.]+\.\s*|match [^.]+\.\s*)"
    r"|\bafter (?:her|his|their) line,\s*"
    r"|\b(?:no contact is shown|preserve [^.]*|hold this angle[^.]*|composite [^.]*|film [^.]*separate passes[^.]*)\.?)",
    re.IGNORECASE,
)

_NON_SUBJECT_WORDS = {
    "after", "before", "while", "when", "then", "meanwhile", "suddenly",
    "in", "on", "at", "as", "from", "beyond", "far", "near", "hold",
}


def _infer_subject(clause: str) -> str | None:
    """Extract the leading subject (name or pronoun) from a clause to repair verb-only splits."""
    m = re.match(r"^(The [A-Z][a-z]+(?: [A-Z][a-z]+)?|[A-Z][a-z]+|He|She|They)\b", clause.strip())
    if not m:
        return None
    candidate = m.group(1)
    if candidate.lower() in _NON_SUBJECT_WORDS:
        return None
    return candidate


def _split_what_we_see_into_frames(text: str) -> list[str]:
    """Split a multi-frame `whatWeSee` description into standalone single-frame AI video prompts."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []

    # Strip non-visual editing/compositing meta-notes
    cleaned = _META_NOTE_RE.sub("", cleaned).strip(" ,;.")
    if not cleaned:
        return []
    cleaned = cleaned[0].upper() + cleaned[1:]

    # 1. Split into sentences first
    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", cleaned) if s.strip()]

    # Merge pure atmospheric/background sentences with the preceding frame
    merged_sentences: list[str] = []
    for sent in raw_sentences:
        if merged_sentences and _ATMOSPHERE_PREFIX_RE.match(sent):
            merged_sentences[-1] = f"{merged_sentences[-1]} {sent}"
        else:
            merged_sentences.append(sent)

    # 2. Within each sentence, split on multi-frame / multi-action connectors
    frames: list[str] = []
    connector_re = re.compile(
        r"\s*;\s+"
        r"|,?\s+\b(?:then|meanwhile)\b[:,]?\s+"
        r"|\s+\b(?:before|while|as)\s+(?=(?:the|a|an|he|she|they|[A-Z][a-z]+)\s+[a-z]+)"
        r"|,\s+and\s+(?=(?:the|a|an|he|she|they|it|[A-Z][a-z]+)\s+[a-z]+)"
        r"|,\s+(?:and\s+)?(?=[a-z]+s\b)",
        re.IGNORECASE,
    )

    last_subject: str | None = None
    for sent in merged_sentences:
        if re.match(r"^Hold\s+(?:as|on)\b", sent, re.IGNORECASE):
            parts = [sent]
        else:
            parts = [p.strip(" ,;") for p in connector_re.split(sent) if p and p.strip(" ,;")]

        for part in parts:
            if len(part) < 4:
                continue
            subj = _infer_subject(part)
            if subj:
                last_subject = subj
            elif last_subject and re.match(r"^[a-z]+s\b", part):
                # Repair verb-only fragment like "flicks a pebble..." -> "He flicks a pebble..."
                part = f"{last_subject} {part}"
            part = part[0].upper() + part[1:]
            if part[-1] not in ".!?":
                part += "."
            frames.append(part)

    return frames or [cleaned]


def _clamp_shot_duration(raw_dur: int, has_dialogue: bool, emotion_text: str) -> int:
    high_emotion = bool(
        re.search(
            r"\b(deep|intense|heartfelt|tearful|emotional|desperate|triumphant|climactic|"
            r"anguish|grief|sorrow|joy|relief|pleading|passionate|trembling|crying|"
            r"determined|courage|moral|hope|love|fear|awe|proud|broken|devastated|revelation)\b",
            emotion_text.lower(),
        )
    )
    if has_dialogue and high_emotion:
        return min(max(raw_dur, 1), 7)
    return min(max(raw_dur, 1), 5)


def _split_multi_frame_shots(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure every shot contains strictly one visual frame; split multi-frame shots into separate shots."""
    for s_idx, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("sceneId") or f"s{s_idx}")
        new_shots: list[dict[str, Any]] = []
        for sh in scene.get("shots") or []:
            if not isinstance(sh, dict):
                continue
            frames = _split_what_we_see_into_frames(str(sh.get("whatWeSee") or ""))
            dur_str = re.sub(r"[^0-9.]", "", str(sh.get("durationSeconds") or "4"))
            parent_dur = int(float(dur_str)) if dur_str else 4
            dlg = sh.get("dialogue")
            has_dialogue = isinstance(dlg, dict) and bool(str(dlg.get("line") or "").strip())
            emotion_text = f"{sh.get('emotion') or ''} {dlg.get('delivery') if isinstance(dlg, dict) else ''}"

            if len(frames) <= 1:
                sh["durationSeconds"] = _clamp_shot_duration(parent_dur, has_dialogue, emotion_text)
                new_shots.append(sh)
                continue

            # Split into N single-frame shots
            per_frame_dur = max(2, min(4, round(parent_dur / len(frames))))
            speaker_name = str(dlg.get("speaker") or "").strip().lower() if isinstance(dlg, dict) else ""
            speaker_first = speaker_name.split()[0] if speaker_name else ""
            dlg_target_idx = 0
            if speaker_name:
                for f_idx, frame_text in enumerate(frames):
                    fl = frame_text.lower()
                    if speaker_name in fl or (speaker_first and speaker_first in fl):
                        dlg_target_idx = f_idx
                        break

            parent_chars = [str(c) for c in (sh.get("characters") or []) if c]
            for f_idx, frame_text in enumerate(frames):
                child = dict(sh)
                child["whatWeSee"] = frame_text
                is_dlg_shot = has_dialogue and (f_idx == dlg_target_idx)
                child["dialogue"] = dlg if is_dlg_shot else None
                if len(parent_chars) > 1:
                    frame_lower = frame_text.lower()
                    matched_chars = [
                        c for c in parent_chars
                        if c.lower() in frame_lower or c.split()[0].lower() in frame_lower
                    ]
                    if is_dlg_shot and isinstance(dlg, dict) and dlg.get("speaker"):
                        sp = str(dlg["speaker"])
                        if sp not in matched_chars and sp in parent_chars:
                            matched_chars.append(sp)
                    child["characters"] = matched_chars or parent_chars[:1]
                child["durationSeconds"] = _clamp_shot_duration(
                    parent_dur if is_dlg_shot else per_frame_dur,
                    is_dlg_shot,
                    emotion_text,
                )
                new_shots.append(child)

        for sh_idx, sh in enumerate(new_shots, start=1):
            sh["shotId"] = f"{scene_id}-sh{sh_idx}"
        scene["shots"] = new_shots

    return scenes

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class MessagePayload(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AIChatRequest(BaseModel):
    messages: list[MessagePayload] = Field(
        ..., description="Full conversation history (user + assistant turns)."
    )
    interview_step: str = Field(
        default="idle",
        description="Current frontend interview step so the AI knows context.",
    )
    story_draft: dict[str, Any] = Field(
        default_factory=dict,
        description="Accumulated story draft fields (title, premise, mood, etc.).",
    )
    intake_state: dict[str, Any] | None = Field(
        default=None,
        description="Confirmed intake state required before invoking story generation.",
    )


class AIChatResponse(BaseModel):
    content: str
    next_step: str
    options: list[dict[str, str]] | None = None
    planner: dict[str, Any] | None = None
    suggested_title: str | None = None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are CINEMIND — an expert AI cinematic story and shot-planning assistant.

Your job is to guide the user through a structured creative interview and ultimately
produce a complete, production-ready shot plan in strict JSON.

Interview flow (use `interview_step` from context to know where you are):
  idle          → Ask about the central conflict / relationship driving the story.
  relationship  → Ask about visual style (cinematic realism, anime, dark fantasy, etc.).
  visual_style  → Ask about mood and emotional arc.
  mood_emotion  → Ask about camera style and ending intention, then generate shot plan.
  camera_ending → Generate the full shot plan.
  planned       → Answer follow-up questions about the existing plan.

Always return a JSON object with EXACTLY these keys:
{
  "content": "<markdown reply to show the user>",
  "next_step": "<one of the interview steps above>",
  "suggested_title": "<short story title or null>",
  "options": [{"id": "opt1", "label": "...", "action": "send"}, ...] or null,
  "planner": <full ShotPlanner JSON object or null>
}

When next_step is "camera_ending" or "planned" and you have enough info, produce a
complete `planner` JSON with this structure (null otherwise):
{
  "id": "planner-<random 8 chars>",
  "isApproved": false,
  "overview": {
    "filmTitle": "...", "logline": "...", "totalScenes": N,
    "totalShots": N, "dialogueLines": N, "runningTimeSeconds": N,
    "videoFormat": "16:9 HD", "frameRate": "24fps", "creatorsIntent": "..."
  },
  "characters": [{"id":"c1","name":"...","role":"...","physicalAppearance":"...","personalityAndVoice":"..."}],
  "locations":  [{"id":"l1","name":"...","visualDescription":"..."}],
  "scenes": [
    {
      "sceneId": "s1", "sceneTitle": "...", "locations": ["..."], "timeOfDay": "...",
      "shots": [
        {
          "shotId": "s1-sh1", "durationSeconds": 4,
          "framing": "Wide Shot (WS)", "cameraMovement": "Static",
          "characters": ["..."], "location": "...", "whatWeSee": "...",
          "dialogue": {"speaker":"...","line":"...","delivery":"..."} or null,
          "emotion": "...", "sound": "..."
        }
      ]
    }
  ]
}

Rules:
- Always return valid JSON only — no markdown code fences, no extra text outside the JSON.
- Keep `content` concise and cinematic — this is shown directly in the chat UI, and briefly state the story's moral lesson.
- NEVER ask repeated questions about details the user already provided (title, visual style, or story context).
- When `intake_state` is confirmed OR `interview_step` is `ready_for_plan` / `camera_ending`, DO NOT ask any more questions: set `next_step` to `"planned"`, `options` to `null`, and generate the complete `planner` with **EXACTLY 3 scenes**.
- Provide 3–4 `options` only when asking an interview question (and `null` when generating the planner).
- **Mandatory 3-Scene Story Structure with Moral** (whenever producing `planner`, `scenes` MUST contain **ONLY 3 scenes**, with **as many single-frame shots as needed — at least 10–18 shots per scene, 30–54+ total shots, NEVER 4–5 shots per scene**):
  1. **Scene 1 (`s1`) — Character Introduction**: Introduce the main character(s), their personality, setting, and daily world.
  2. **Scene 2 (`s2`) — Main Plot**: Present the central conflict, challenge, or turning point driving the story.
  3. **Scene 3 (`s3`) — Climax & Moral**: Deliver the dramatic climax, resolve the conflict, and clearly express the **moral of the story** (and reflect the moral in `overview.creatorsIntent`).
- **Always use full proper names (NEVER IDs)**: In `scenes[].locations`, `shots[].location`, `shots[].characters`, and `shots[].dialogue.speaker`, ALWAYS write the full human-readable location name and character name (e.g., `"Starlit Meadow"`, `"Pip the Rabbit"`), NEVER short IDs like `"l1"`, `"l2"`, `"c1"`, `"c2"`.
- **AI Video Generation Shot Pacing & Duration Rule (STRICT HARD LIMIT)**:
  - **1 SHOT = 1 FRAME = 1 CHARACTER FOCUS & 1 ACTION (ABSOLUTE RULE)**: Every shot is a standalone 2–5s AI video generation clip (Veo / Runway / Kling). AI video generators BREAK, morph, and drop actions if asked to render 2–4 frames or multiple characters doing separate actions in one clip.
  - **NEVER combine 2+ frames, 2+ sequential actions, or 2+ characters doing separate actions in one shot**:
    - BAD (multi-frame & multi-character — FORBIDDEN): `"Ben drops his hammer and bolts up the lane. Villagers abandon their work and follow; Mara gathers her skirt and sets off behind them."`
    - GOOD (1 frame, 1 subject focus per shot):
      - Shot 1 (Ben): `"Ben drops his heavy blacksmith hammer onto the anvil and bolts toward the uphill lane, eyes wide with alarm."`
      - Shot 2 (Villagers): `"Startled villagers in the cobbled square drop their baskets and hurry toward the uphill lane."`
      - Shot 3 (Mara): `"Mara gathers the hem of her dark wool skirt and hurries briskly up the stone lane after them."`
    - NEVER put editing/compositing notes like `"Cut ahead to"`, `"After a cut to night"`, `"Preserve the composition"`, `"Composite..."`, or `"Separate passes"` inside `whatWeSee`.
    - NEVER use `"then"`, `"before"`, `"meanwhile"`, semicolons `;`, or 2–3 sequential events in one `whatWeSee`.
  - **NEVER restrict a scene to 4–5 shots.** Break every scene into **as many shots as needed (minimum 10–18+ single-frame shots per scene, no upper limit)** so every visual beat, action, and character reaction is its own clean AI video clip.
  - **STRICT**: Every shot MUST be **5 seconds or less (`durationSeconds <= 5`)**, ideally **2–4 seconds**. NEVER generate a shot longer than 5 seconds for action, establishing, insert, or reaction shots.
  - **ABSOLUTE MAXIMUM = 7 SECONDS**: ONLY a shot with **spoken `dialogue` carrying deep, high emotion** (e.g., heartfelt confession, climax plea, grief, or moral realization) may exceed 5 seconds, and its **maximum allowed duration is 7 seconds (`<= 7`, NEVER 8, 9, or 10 seconds)**.
- **Rich Visuals, Movement Speed & Background Emotion (`whatWeSee` & `emotion`)**:
  - Make every `whatWeSee` description vivid and specific to that **single frame** (1–2 sentences describing only that one moment + its environment). NEVER write generic summaries like `"A boy walks."`
  - **Match body language & speed to emotion**: Explicitly describe *how* and at *what speed/pace* the character moves, their posture, facial expression, and eye line (e.g., if serious, he walks with slow, heavy, deliberate footsteps, jaw set, shoulders tense, gaze locked forward; if happy, he walks with a light, brisk, bouncy stride, arms swinging freely, bright eyes, and an open smile).
  - **Detail the background & atmosphere**: Describe foreground/background elements, lighting color, shadows, weather, and movement in the environment of that single frame so the background visually reinforces the mood (e.g., cool desaturated mist and still silhouettes for tension vs. warm golden sunlight, swaying leaves, and vibrant depth for joy).
  - In `emotion`, state both the character's felt/visible emotion and the background's emotional atmosphere.
"""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=AIChatResponse, status_code=status.HTTP_200_OK)
async def ai_chat(body: AIChatRequest) -> AIChatResponse:
    """Send a conversation to OpenAI and return a structured CINEMIND reply."""
    if body.intake_state is not None:
        confirmed = bool(body.intake_state.get("confirmed"))
        has_all_fields = all(
            bool(str(body.intake_state.get(k) or "").strip())
            for k in ("story_title", "visual_style", "story_context")
        )
        if not (confirmed and has_all_fields):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Story intake must collect and confirm title, visual_style, and story_context before story generation.",
            )

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured in backend/.env.",
        )
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Build messages for OpenAI
    intake_confirmed = bool(body.intake_state and body.intake_state.get("confirmed"))
    effective_step = "ready_for_plan" if (intake_confirmed and body.interview_step == "idle") else body.interview_step

    system_context = (
        f"Current interview_step: {effective_step}\n"
        f"Story draft so far: {json.dumps(body.story_draft, ensure_ascii=False)}"
    )
    if intake_confirmed and body.intake_state:
        needs_doc_title = bool(body.story_draft.get("titleNeedsExtractionFromDoc"))
        sanitized_intake = dict(body.intake_state)
        if needs_doc_title:
            sanitized_intake["story_title"] = "<EXTRACT_ACTUAL_TITLE_FROM_STORY_TEXT>"
        title_note = (
            "IMPORTANT: Do NOT use any filename as the title. Extract the ACTUAL story title "
            "from inside `story_context` (or give it a fitting literary title based on the story) "
            "and put it in both `suggested_title` and `planner.overview.filmTitle`. "
            if needs_doc_title
            else ""
        )
        system_context += (
            f"\nConfirmed intake_state: {json.dumps(sanitized_intake, ensure_ascii=False)}\n"
            f"{title_note}"
            "INSTRUCTION: Title, visual style, and story context are ALREADY confirmed. "
            "Do NOT ask any more interview questions. Immediately set next_step='planned', "
            "options=null, and generate the complete `planner` JSON with ONLY 3 scenes: "
            "Scene 1 = character introduction, Scene 2 = main plot, Scene 3 = climax and moral of the story. "
            "CRITICAL AI VIDEO RULE: Do NOT limit scenes to 4 shots. Generate as many shots as needed "
            "(minimum 10-18 single-frame shots per scene) with STRICTLY 1 frame and 1 character focus/action per shot, "
            "and durationSeconds <= 5 (<= 7 only for high-emotion dialogue)."
        )

    openai_messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + system_context},
        *[{"role": m.role, "content": m.content} for m in body.messages],
    ]

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=openai_messages,  # type: ignore[arg-type]
            response_format={"type": "json_object"},
            max_completion_tokens=8192,
        )
        raw = response.choices[0].message.content or "{}"
    except OpenAIError as exc:
        logger.error("OpenAI API error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI error: {exc}",
        ) from exc

    try:
        data = _extract_json(raw)
    except ValueError as exc:
        logger.error("Could not parse AI JSON response: %s", raw[:300])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned malformed JSON.",
        ) from exc

    planner_raw = data.get("planner")
    if isinstance(planner_raw, dict) and isinstance(planner_raw.get("scenes"), list):
        # Resolve any l1/l2 or c1/c2 IDs in scenes/shots to proper human-readable names
        loc_map: dict[str, str] = {}
        for loc in planner_raw.get("locations") or []:
            if isinstance(loc, dict) and loc.get("id") and loc.get("name"):
                loc_map[str(loc["id"]).strip().lower()] = str(loc["name"]).strip()

        char_map: dict[str, str] = {}
        for ch in planner_raw.get("characters") or []:
            if isinstance(ch, dict) and ch.get("id") and ch.get("name"):
                char_map[str(ch["id"]).strip().lower()] = str(ch["name"]).strip()

        def _resolve_name(val: Any, mapping: dict[str, str]) -> str:
            text = str(val or "").strip()
            return mapping.get(text.lower(), text)

        # Enforce strictly 3 scenes max and keep overview totals consistent
        scenes = planner_raw["scenes"][:3]
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            if isinstance(scene.get("locations"), list):
                scene["locations"] = [
                    _resolve_name(loc, loc_map) for loc in scene["locations"] if loc
                ]
            for sh in scene.get("shots") or []:
                if not isinstance(sh, dict):
                    continue
                if sh.get("location"):
                    sh["location"] = _resolve_name(sh["location"], loc_map)
                if isinstance(sh.get("characters"), list):
                    sh["characters"] = [
                        _resolve_name(ch, char_map) for ch in sh["characters"] if ch
                    ]
                if isinstance(sh.get("dialogue"), dict) and sh["dialogue"].get("speaker"):
                    sh["dialogue"]["speaker"] = _resolve_name(
                        sh["dialogue"]["speaker"], char_map
                    )
        # Split any multi-frame shots into 1-frame-per-shot and enforce duration caps
        raw_shot_count = sum(len(s.get("shots", [])) for s in scenes if isinstance(s, dict))
        scenes = _split_multi_frame_shots(scenes)
        split_shot_count = sum(len(s.get("shots", [])) for s in scenes if isinstance(s, dict))
        logger.info("Shot planner post-processed: %d -> %d shots across %d scenes", raw_shot_count, split_shot_count, len(scenes))
        planner_raw["scenes"] = scenes
        if isinstance(planner_raw.get("overview"), dict):
            total_shots = sum(
                len(s.get("shots", [])) for s in scenes if isinstance(s, dict)
            )
            dialogue_lines = sum(
                1
                for s in scenes
                if isinstance(s, dict)
                for sh in s.get("shots", [])
                if isinstance(sh, dict) and sh.get("dialogue")
            )
            running_time = sum(
                int(sh.get("durationSeconds") or 0)
                for s in scenes
                if isinstance(s, dict)
                for sh in s.get("shots", [])
                if isinstance(sh, dict)
            )
            planner_raw["overview"]["totalScenes"] = len(scenes)
            planner_raw["overview"]["totalShots"] = total_shots
            planner_raw["overview"]["dialogueLines"] = dialogue_lines
            planner_raw["overview"]["runningTimeSeconds"] = running_time

        # Generate 1 reference storyboard image for Scene 1 in the requested animation/visual style
        visual_style = (
            (body.intake_state or {}).get("visual_style")
            or body.story_draft.get("visualStyle")
            or "Cinematic realism"
        )
        film_title = (
            (planner_raw.get("overview") or {}).get("filmTitle")
            or (body.intake_state or {}).get("story_title")
            or "Untitled Story"
        )

        async def _attach_scene_image(scene: dict[str, Any]) -> None:
            if not isinstance(scene, dict) or not settings.GEMINI_API_KEY:
                return
            shots = scene.get("shots") or []
            first_shot = shots[0] if shots and isinstance(shots[0], dict) else {}
            locations = ", ".join(scene.get("locations") or []) or "atmospheric setting"
            time_of_day = scene.get("timeOfDay") or "day"
            visual_cue = first_shot.get("whatWeSee") or scene.get("sceneTitle") or ""
            emotion = first_shot.get("emotion") or ""
            prompt = (
                f"In {visual_style} animation style: cinematic storyboard frame for '{film_title}'. "
                f"Scene: {scene.get('sceneTitle', '')}. Setting: {locations}, {time_of_day}. "
                f"Visual action: {visual_cue}. Mood: {emotion}. "
                f"Strictly render in {visual_style} style, rich composition, dramatic lighting, no text, no watermarks."
            )[:950]

            api_key = settings.GEMINI_API_KEY.strip()
            async with httpx.AsyncClient(timeout=45.0) as http:
                # 1. Try Imagen 3 (:predict)
                try:
                    resp = await http.post(
                        "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict",
                        params={"key": api_key},
                        json={
                            "instances": [{"prompt": prompt}],
                            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
                        },
                    )
                    if resp.status_code == 200:
                        preds = resp.json().get("predictions") or []
                        if preds and preds[0].get("bytesBase64Encoded"):
                            mime = preds[0].get("mimeType") or "image/png"
                            b64 = preds[0]["bytesBase64Encoded"]
                            scene["referenceImageUrl"] = f"data:{mime};base64,{b64}"
                            scene["referenceImagePrompt"] = prompt
                            return
                    else:
                        logger.warning(
                            "Gemini imagen-3.0-generate-002 returned %s: %s",
                            resp.status_code,
                            resp.text[:250],
                        )
                except Exception as exc:
                    logger.warning("Gemini imagen-3.0-generate-002 failed: %s", exc)

                # 2. Fallback to Gemini native image generation (:generateContent)
                for gemini_model in (
                    "gemini-2.5-flash-image",
                    "gemini-2.0-flash-exp-image-generation",
                ):
                    try:
                        resp = await http.post(
                            f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent",
                            params={"key": api_key},
                            json={
                                "contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
                            },
                        )
                        if resp.status_code == 200:
                            candidates = resp.json().get("candidates") or []
                            for cand in candidates:
                                parts = (cand.get("content") or {}).get("parts") or []
                                for part in parts:
                                    inline = part.get("inlineData") or part.get("inline_data")
                                    if inline and inline.get("data"):
                                        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                                        scene["referenceImageUrl"] = f"data:{mime};base64,{inline['data']}"
                                        scene["referenceImagePrompt"] = prompt
                                        return
                        else:
                            logger.warning(
                                "Gemini %s returned %s: %s",
                                gemini_model,
                                resp.status_code,
                                resp.text[:250],
                            )
                    except Exception as exc:
                        logger.warning("Gemini %s failed: %s", gemini_model, exc)

        if scenes:
            await _attach_scene_image(scenes[0])

    suggested_title_raw = data.get("suggested_title")

    return AIChatResponse(
        content=str(data.get("content") or ""),
        next_step=str(data.get("next_step") or body.interview_step),
        options=_normalize_options(data.get("options")),
        planner=planner_raw if isinstance(planner_raw, dict) else None,
        suggested_title=str(suggested_title_raw).strip() if suggested_title_raw else None,
    )


# ---------------------------------------------------------------------------
# Adaptive Story Intake Analyzer Endpoint
# ---------------------------------------------------------------------------

class IntakeStateSnapshot(BaseModel):
    story_title: str | None = None
    visual_style: str | None = None
    story_context: str | None = None
    current_question: str | None = None
    status: str = "collecting"


class IntakeAnalyzeRequest(BaseModel):
    message: str = Field(..., min_length=1)
    input_source: str = Field(default="text")
    current_state: IntakeStateSnapshot = Field(default_factory=IntakeStateSnapshot)
    recent_history: list[MessagePayload] = Field(default_factory=list)


class IntakeAnalysisPayload(BaseModel):
    input_source: str = "text"
    intent: str
    extracted_fields: dict[str, Any]
    missing_fields: list[str]
    next_action: str


class IntakeConversationPayload(BaseModel):
    assistant_message: str


class IntakeAnalyzeResponse(BaseModel):
    analysis: IntakeAnalysisPayload
    conversation: IntakeConversationPayload


INTAKE_SYSTEM_PROMPT = """You are CINEMIND, a warm, thoughtful creative writing partner helping a creator shape their story before generating scenes.

You must produce TWO strictly separated sections in valid JSON:
1. `analysis` (INTERNAL data only — never shown to the user):
   - Extract ONLY what the user explicitly provided or clearly implied given `current_state`.
   - Never invent a `story_title` or `story_context` for generic requests like "Tell me a story." or "Give me a story.". Return null for missing fields.
   - Classify `intent` as one of:
     create_story, answer_question, modify_story_title, modify_visual_style, modify_story_context, add_context, confirm_intake, request_edit, suggest_title, explain_story_first, general_question.
   - `next_action`: one of ask_title, ask_visual_style, ask_story_context, request_confirmation, suggest_titles, clarify.

2. `conversation` (USER-FACING message):
   - `assistant_message` is the ONLY text displayed in chat.
   - Write directly to the creator in natural, friendly, conversational language ("I", "you", "we").
   - Acknowledge what the user just shared, stay consistent with previously collected details, and ask ONE helpful follow-up question at a time.
   - NEVER include third-person commentary like "The user wants..." or "The user asks...".
   - NEVER mention internal field names (story_title, visual_style, story_context, missing_fields), JSON, or extraction logic.
   - When all three details are collected, summarize the story naturally in short prose and ask if they are ready to start building it — do NOT generate the full story yet.

Return strict JSON ONLY with this exact shape:
{
  "analysis": {
    "intent": "...",
    "extracted_fields": {
      "story_title": {"value": "... or null", "confidence": 0.0-1.0},
      "visual_style": {"value": "... or null", "confidence": 0.0-1.0, "details": {}},
      "story_context": {"value": "... or null", "confidence": 0.0-1.0, "theme": "... or null", "main_conflict": "... or null"}
    },
    "missing_fields": ["story_title" | "visual_style" | "story_context"],
    "next_action": "..."
  },
  "conversation": {
    "assistant_message": "..."
  }
}"""


def _looks_like_internal_analysis(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return True
    if lowered.startswith("{") or lowered.startswith("["):
        return True
    forbidden_patterns = (
        "the user ",
        "user wants ",
        "user asks ",
        "missing_fields",
        "story_title",
        "visual_style",
        "story_context",
        "next_action",
        "missing field:",
    )
    return any(pat in lowered for pat in forbidden_patterns)


def _fallback_natural_message(
    extracted: dict[str, Any],
    missing_fields: list[str],
    current_state: IntakeStateSnapshot,
) -> str:
    title = (extracted.get("story_title") or {}).get("value") or current_state.story_title
    style = (extracted.get("visual_style") or {}).get("value") or current_state.visual_style
    context = (extracted.get("story_context") or {}).get("value") or current_state.story_context

    if not missing_fields and title and style and context:
        return (
            f"That sounds like a compelling direction! So we're creating **{title}**, "
            f"with a {style.lower()} visual style, about {context[0].lower() + context[1:] if len(context) > 1 else context}.\n\n"
            "Shall we start building the story?"
        )
    if "story_title" in missing_fields:
        if style:
            return f"Love that {style.lower()} direction! Do you already have a title in mind, or would you like me to suggest one?"
        return "Of course! I'd love to help you create one. Let's start with a title. Do you already have a name in mind, or would you like me to suggest one?"
    if "visual_style" in missing_fields:
        return "What kind of visual world are you imagining for this story? Something cinematic, anime-inspired, dark fantasy, or another style?"
    return f"Now tell me a little about the story itself. What's happening in {title or 'your story'}? You can share just a rough idea, and we'll develop it together."


@router.post(
    "/intake/analyze",
    response_model=IntakeAnalyzeResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_story_intake(body: IntakeAnalyzeRequest) -> IntakeAnalyzeResponse:
    """Analyze a user message internally and return a separate natural conversational reply."""
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured in backend/.env.",
        )

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    context_summary = (
        f"Current intake state: {body.current_state.model_dump_json()}\n"
        f"Latest user message: {body.message}"
    )

    openai_messages = [
        {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
        *[{"role": m.role, "content": m.content} for m in body.recent_history[-6:]],
        {"role": "user", "content": context_summary},
    ]

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=openai_messages,  # type: ignore[arg-type]
            response_format={"type": "json_object"},
            max_completion_tokens=800,
        )
        raw = response.choices[0].message.content or "{}"
    except OpenAIError as exc:
        logger.error("OpenAI intake analyze error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI error: {exc}",
        ) from exc

    try:
        data = _extract_json(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI intake analyzer returned malformed JSON.",
        ) from exc

    analysis_raw = data.get("analysis") if isinstance(data.get("analysis"), dict) else data
    conversation_raw = (
        data.get("conversation") if isinstance(data.get("conversation"), dict) else {}
    )

    extracted = (
        analysis_raw.get("extracted_fields")
        if isinstance(analysis_raw.get("extracted_fields"), dict)
        else {}
    )
    missing_raw = analysis_raw.get("missing_fields")
    missing = [str(m) for m in missing_raw] if isinstance(missing_raw, list) else []
    assistant_msg = str(conversation_raw.get("assistant_message") or "").strip()

    if _looks_like_internal_analysis(assistant_msg):
        assistant_msg = _fallback_natural_message(extracted, missing, body.current_state)

    return IntakeAnalyzeResponse(
        analysis=IntakeAnalysisPayload(
            input_source=body.input_source,
            intent=str(analysis_raw.get("intent") or "create_story"),
            extracted_fields=extracted,
            missing_fields=missing,
            next_action=str(analysis_raw.get("next_action") or "ask_title"),
        ),
        conversation=IntakeConversationPayload(
            assistant_message=assistant_msg,
        ),
    )


# ---------------------------------------------------------------------------
# Document Text Extraction Endpoint (PDF / DOCX / TXT)
# ---------------------------------------------------------------------------

class ExtractDocumentRequest(BaseModel):
    filename: str
    content_base64: str


class ExtractDocumentResponse(BaseModel):
    text: str


def _extract_docx_text(raw_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for p in root.iter():
        if p.tag.endswith("}p"):
            texts = [t.text for t in p.iter() if t.tag.endswith("}t") and t.text]
            if texts:
                paragraphs.append("".join(texts))
    return "\n".join(paragraphs).strip()


def _extract_pdf_text_builtin(raw_bytes: bytes) -> str:
    """Best-effort pure-Python PDF text extraction (pypdf if installed, else FlateDecode)."""
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        joined = "\n".join(pages).strip()
        if joined:
            return joined
    except Exception:
        pass

    chunks: list[str] = []
    for stream_match in re.finditer(rb"stream(?:\r\n|\r|\n)([\s\S]*?)(?:\r\n|\r|\n)?endstream", raw_bytes):
        stream_data = stream_match.group(1)
        try:
            decoded = zlib.decompress(stream_data).decode("latin-1", errors="ignore")
        except Exception:
            decoded = stream_data.decode("latin-1", errors="ignore")

        def _decode_hex(hex_str: str) -> str:
            cleaned = re.sub(r"\s+", "", hex_str)
            if len(cleaned) % 2 == 1:
                cleaned += "0"
            try:
                b = bytes.fromhex(cleaned)
                if b.startswith(b"\xfe\xff"):
                    return b[2:].decode("utf-16-be", errors="ignore")
                if len(b) >= 2 and b[0] == 0:
                    return b.decode("utf-16-be", errors="ignore")
                return b.decode("latin-1", errors="ignore")
            except Exception:
                return ""

        for lit in re.findall(r"\(([^()\\]*(?:\\.[^()\\]*)*)\)\s*Tj", decoded):
            chunks.append(lit.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\"))
        for hx in re.findall(r"<([0-9A-Fa-f\s]+)>\s*Tj", decoded):
            val = _decode_hex(hx)
            if val:
                chunks.append(val)
        for arr in re.findall(r"\[(.*?)\]\s*TJ", decoded, flags=re.DOTALL):
            for token in re.finditer(r"\(([^()\\]*(?:\\.[^()\\]*)*)\)|<([0-9A-Fa-f\s]+)>", arr):
                if token.group(1) is not None:
                    chunks.append(
                        token.group(1).replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
                    )
                elif token.group(2) is not None:
                    val = _decode_hex(token.group(2))
                    if val:
                        chunks.append(val)
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()


@router.post(
    "/extract-document",
    response_model=ExtractDocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_document(body: ExtractDocumentRequest) -> ExtractDocumentResponse:
    """Extract story text from an uploaded PDF, DOCX, or TXT file."""
    try:
        raw_bytes = base64.b64decode(body.content_base64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 document payload.",
        ) from exc

    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else ""
    text = ""

    if ext == "txt":
        text = raw_bytes.decode("utf-8", errors="ignore").strip()
    elif ext == "docx":
        try:
            text = _extract_docx_text(raw_bytes)
        except Exception as exc:
            logger.warning("DOCX extraction failed: %s", exc)
    elif ext == "pdf":
        text = _extract_pdf_text_builtin(raw_bytes)

    return ExtractDocumentResponse(text=text[:15000])

