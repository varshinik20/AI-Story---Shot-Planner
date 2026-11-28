"""Adaptive Story Intake Engine: unified context analysis for text, voice, and document inputs."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid
from typing import Sequence

from app.engines.story_intake.schemas import (
    InputSourceType,
    IntakeAnalysisResult,
    IntakeState,
    LLMIntakeExtractionPayload,
)
from app.services.llm_service import LLMService

DEFAULT_STYLE_OPTIONS = [
    "Pixar / Animated",
    "Realistic Cinematic Film",
    "Anime / Hand-Drawn",
    "Noir / High-Contrast Thriller",
    "Documentary Naturalistic",
    "Stop-Motion Miniature",
]

_INTERNAL_LEAK_PATTERNS = (
    re.compile(r"\bthe user\b", re.IGNORECASE),
    re.compile(r"\buser asks\b", re.IGNORECASE),
    re.compile(r"\buser provided\b", re.IGNORECASE),
    re.compile(r"\buser wants\b", re.IGNORECASE),
    re.compile(r"\bmissing[-_ ]fields?\b", re.IGNORECASE),
    re.compile(r"\bstory_title\b|\bvisual_style\b|\bstory_context\b|\bnext_action\b", re.IGNORECASE),
    re.compile(r"\bintent classification\b", re.IGNORECASE),
    re.compile(r"\bintake analysis\b", re.IGNORECASE),
    re.compile(r"\bjson extraction\b", re.IGNORECASE),
)

_CONFIRMATION_WORDS = re.compile(
    r"^(?:[\s,!.]*(?:yes|yeah|yep|yup|sure|confirm(?:ed)?|looks good|sounds good|go ahead|proceed|perfect|correct|that'?s right|ok(?:ay)?|let'?s do it|let'?s start|start building(?: the story)?|create it|build it|please))+[\s,!.]*$",
    re.IGNORECASE,
)


def _looks_like_internal_analysis(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.startswith("{") and stripped.endswith("}"):
        return True
    return any(pattern.search(stripped) for pattern in _INTERNAL_LEAK_PATTERNS)


def _normalize_whitespace(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _strip_meta_command(text: str) -> str:
    """Remove trailing command clauses like 'Now create a story.' when saving raw premise."""
    cleaned = re.sub(
        r"\b(now\s+)?(please\s+)?(create|write|make|generate|build)\s+(a|the|this)?\s*story[.! ]*$",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or text.strip()


_GENERIC_REQUEST_WORDS: frozenset[str] = frozenset(
    """
    a an the any some one new my me us our for to of with please pls kindly just now again also
    can could would will shall should may might you u i im i'm id i'd we lets let's let want wanna
    need like love help hey hi hello ok okay so then and or
    generate create write make tell give build produce draft craft come up do get
    story stories tale tales film movie short animation animated script plot idea something
    cool nice good great fun funny interesting amazing awesome random small little quick simple
    kid kids children child bedtime
    """.split()
)


_FIELD_LABEL_WORDS: frozenset[str] = frozenset(
    "title titled called named name is it's its be style styled visual look looks animation 2d 3d".split()
)


def _is_generic_story_request(text: str | None, *, known_values: tuple[str | None, ...] = ()) -> bool:
    """True when the text carries no narrative content usable as a premise.

    Words that only ask for a story, label a field ("the title is ..."), or repeat an already-known
    title / visual style are ignored; if nothing remains, the text is not a premise.

    e.g. "can you generate a story for me"                      -> True
         "The title is The Moonlight Guardian" (title known)   -> True
         "a brave fox protects the forest at night"            -> False
    """
    if not text or not text.strip():
        return True
    ignored = set(_GENERIC_REQUEST_WORDS) | set(_FIELD_LABEL_WORDS)
    for value in known_values:
        if value:
            ignored.update(re.findall(r"[a-z0-9']+", value.lower()))
    tokens = re.findall(r"[a-z0-9']+", text.lower())
    return all(tok in ignored for tok in tokens)


def _title_grounded_in_input(
    candidate: str | None,
    latest_message: str,
    prior_suggestions: list[str],
    existing_title: str | None,
) -> bool:
    if not candidate:
        return False
    cand_low = candidate.strip().lower()
    if existing_title and cand_low == existing_title.strip().lower():
        return True
    if any(cand_low == s.strip().lower() for s in prior_suggestions):
        # User must mention it or select it by index/wording
        msg_low = latest_message.lower()
        if cand_low in msg_low:
            return True
        words = [w for w in re.findall(r"[a-z0-9]+", cand_low) if len(w) > 2]
        if words and all(w in msg_low for w in words[:2]):
            return True
    msg_low = latest_message.lower()
    if cand_low in msg_low:
        return True
    # Check explicit title phrasing ("title it X", "called X", "titled X")
    title_match = re.search(
        r"(?:title(?:\s+it|\s+is)?|called|named|titled)\s+[\"']?([^\"'\n.?!]{2,80})[\"']?",
        latest_message,
        re.IGNORECASE,
    )
    if title_match:
        return True
    # Single concise title reply when user wasn't describing plot actions
    words = cand_low.split()
    if 1 <= len(words) <= 6 and all(w in msg_low for w in words):
        # Avoid mistaking action sentences ("the girl was running...") for a title
        action_markers = ("running", "falling", "fell", "walked", "decided", "wanted", "towards", "because")
        if not any(m in msg_low for m in action_markers):
            return True
    return False


def _build_natural_fallback(state: IntakeState, missing: list[str], is_document: bool) -> str:
    if not missing:
        return (
            f'Here is what I have so far:\n'
            f'- **Title:** "{state.story_title}"\n'
            f'- **Visual Style:** {state.visual_style}\n'
            f'- **Story Premise:** {state.story_context}\n\n'
            f'Does everything look right to start developing the story?'
        )

    ack = ""
    if is_document and state.extracted_from_filename:
        ack = f'I\'ve read "{state.extracted_from_filename}" and captured your story! '
    elif state.story_context and not state.story_title and not state.visual_style:
        ack = "That's a gripping premise — I've got the story context noted. "
    elif state.story_title and state.visual_style and not state.story_context:
        ack = f'Great, "{state.story_title}" in a {state.visual_style} style sounds compelling! '
    elif state.story_title and not state.visual_style:
        ack = f'"{state.story_title}" is a strong title. '

    next_field = missing[0]
    if next_field == "story_title":
        if not state.visual_style and not state.story_context and not is_document:
            return (
                "Of course! I'd love to help you create one. Let's start with a title. "
                "Do you already have a name in mind, or would you like me to suggest a few?"
            )
        return f"{ack}What would you like to title this story? (If you'd like, I can suggest a few titles too.)".strip()
    if next_field == "visual_style":
        return (
            f"{ack}What visual style are you envisioning for this film "
            f"(for example, Realistic Cinematic Film, Pixar / Animated, Anime, or Dark Fantasy)?"
        ).strip()
    if state.story_title:
        return (
            f"{ack}Now tell me a little about the story itself. What's happening in "
            f"{state.story_title}? You can share just a rough idea, and we'll develop it together."
        ).strip()
    return f"{ack}What happens in the story? Share the core premise, characters, or key events you have in mind.".strip()


SYSTEM_PROMPT = """You are CINEMIND / StoryForge, a thoughtful, friendly creative director and filmmaking partner helping a creator plan a story and cinematic shot plan.

Your task for this turn:
1. Read the conversation history, the previously collected intake state, and the creator's latest message (which may come from typed text, voice transcription, or an uploaded story document).
2. Extract ONLY what the creator actually stated or explicitly confirmed for these three required fields:
   - extracted_story_title: ONLY if the creator explicitly gave a title or selected one of your suggested titles. NEVER invent a title and pretend the creator chose it! If none was given, return null and explicit_title_provided=false.
   - extracted_visual_style: The visual/cinematic style (e.g., Cinematic Realism, Pixar 3D Animation, Anime, Noir, Stop-Motion, Documentary) ONLY if stated or selected.
   - extracted_story_context: The plot premise, characters, setting, or uploaded narrative text. If existing story_context is already stored, preserve and enrich it rather than erasing it. If the user sends a story premise followed by "create a story" (like "The girl was running towards the edge of the cliff and fell down. Now create a story."), store the cliff-fall premise in extracted_story_context and leave title/style null unless specified.
3. Also determine:
   - is_confirming: true ONLY if all 3 fields are already filled (or filled now) and the user is confirming the summary to proceed.
   - requests_title_suggestions: true if the user asks you to suggest/recommend titles. Return 3-4 vivid options in suggested_titles.
   - requests_style_suggestions: true if the user asks for visual style options.
4. Write natural_response:
   - Speak directly to the creator as a creative partner ("you", "I", "we").
   - NEVER refer to "the user", internal intent classification, missing_fields, JSON keys, or workflow steps.
   - Ask for ONE missing detail naturally at a time.
   - Never ask again for a field that is already collected.
   - If all 3 fields are collected and not yet confirmed by the creator, summarize Title, Visual Style, and Premise concisely and ask the creator to confirm before generating the story.

Return strict JSON matching the schema."""


class StoryIntakeEngine:
    """Analyzes creator input across text, voice, and document channels via LLMService."""

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    async def process_turn(
        self,
        *,
        project_id: uuid.UUID | None,
        latest_message: str,
        existing_state: IntakeState,
        history: Sequence[dict[str, str]],
        input_source: InputSourceType = "text",
        uploaded_filename: str | None = None,
        explicit_title: str | None = None,
        explicit_visual_style: str | None = None,
    ) -> IntakeAnalysisResult:
        state = existing_state.model_copy(deep=True)
        if input_source not in state.input_sources_seen:
            state.input_sources_seen.append(input_source)
        if uploaded_filename:
            state.extracted_from_filename = uploaded_filename
        if explicit_title and explicit_title.strip():
            state.story_title = explicit_title.strip()
            state.title_confirmed = True
        if explicit_visual_style and explicit_visual_style.strip():
            state.visual_style = explicit_visual_style.strip()

        trimmed_input = latest_message.strip()

        # Fast-path clean confirmation check if all 3 fields are already collected and awaiting confirmation
        if state.is_complete() and state.awaiting_confirmation and _CONFIRMATION_WORDS.match(trimmed_input):
            state.confirmed_by_creator = True
            state.awaiting_confirmation = False
            state.title_confirmed = True
            state.confirmation_status = "confirmed"
            state.generation_status = "started"
            state.current_stage = "ready_for_generation"
            state.updated_at = datetime.now(timezone.utc).isoformat()
            reply_msg = (
                f'Wonderful — we\'re locked in on **"{state.story_title}"** ({state.visual_style}). '
                "I'll start shaping your collaborative story draft now."
            )
            state.last_assistant_question = reply_msg
            return IntakeAnalysisResult(
                intent="confirm_intake",
                intake_state=state,
                missing_fields=[],
                next_question_field=None,
                ready_for_story_development=True,
                needs_confirmation=False,
                assistant_message=reply_msg,
            )

        context_snapshot = {
            "existing_intake_state": state.model_dump(),
            "input_source": input_source,
            "uploaded_filename": uploaded_filename,
        }
        history_snippet = list(history[-10:])
        prompt_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history_snippet,
            {
                "role": "user",
                "content": (
                    f"Current stored state:\n{context_snapshot}\n\n"
                    f"Latest creator message ({input_source}):\n{trimmed_input}\n\n"
                    "Return JSON with fields: intent, extracted_story_title, explicit_title_provided, "
                    "extracted_visual_style, extracted_story_context, extracted_dialogue_source, "
                    "is_confirming, requests_title_suggestions, requests_style_suggestions, "
                    "suggested_titles, natural_response."
                ),
            },
        ]

        extracted, _ = await self.llm.generate_json(
            messages=prompt_messages,
            schema_model=LLMIntakeExtractionPayload,
            engine="story_intake",
            operation=f"intake_{input_source}",
            project_id=project_id,
            temperature=0.35,
            max_tokens=900,
        )

        # Apply updates carefully without overwriting confirmed values or accepting invented titles
        cand_title = _normalize_whitespace(extracted.extracted_story_title)
        if cand_title and (
            extracted.explicit_title_provided
            or _title_grounded_in_input(cand_title, trimmed_input, state.suggested_titles, state.story_title)
        ):
            if _title_grounded_in_input(cand_title, trimmed_input, state.suggested_titles, state.story_title):
                state.story_title = cand_title
                state.title_confirmed = True

        cand_style = _normalize_whitespace(extracted.extracted_visual_style)
        if cand_style:
            state.visual_style = cand_style

        cand_context = _normalize_whitespace(extracted.extracted_story_context)
        known_values = (state.story_title, state.visual_style)
        if _is_generic_story_request(cand_context, known_values=known_values):
            # "generate a story for me" is a request, not a premise; never accept it as story_context.
            cand_context = None
        if input_source == "document" and trimmed_input:
            # Preserve exact uploaded story content verbatim
            state.story_context = trimmed_input
        elif cand_context:
            if not state.story_context:
                state.story_context = cand_context
            elif extracted.intent == "edit_details":
                state.story_context = cand_context
            elif cand_context.lower() not in state.story_context.lower() and len(cand_context) > len(state.story_context):
                state.story_context = cand_context
        elif not state.story_context and len(trimmed_input.split()) >= 5:
            # Guard against losing narrative input like "The girl was running towards the edge of the cliff..."
            cleaned_premise = _strip_meta_command(trimmed_input)
            if cleaned_premise and not _is_generic_story_request(cleaned_premise, known_values=known_values):
                state.story_context = cleaned_premise

        if extracted.extracted_dialogue_source:
            state.dialogue_source = extracted.extracted_dialogue_source

        if extracted.suggested_titles:
            state.suggested_titles = [t.strip() for t in extracted.suggested_titles if t.strip()][:5]

        missing = state.missing_fields()
        needs_confirmation = False
        ready_for_story = False

        if not missing:
            if extracted.is_confirming and not extracted.requests_title_suggestions and not extracted.requests_style_suggestions:
                state.confirmed_by_creator = True
                state.awaiting_confirmation = False
                state.confirmation_status = "confirmed"
                state.generation_status = "started"
                state.current_stage = "ready_for_generation"
                ready_for_story = True
            else:
                state.awaiting_confirmation = True
                state.confirmed_by_creator = False
                state.confirmation_status = "not_confirmed"
                state.generation_status = "not_started"
                state.current_stage = "awaiting_confirmation"
                needs_confirmation = True
        else:
            state.awaiting_confirmation = False
            state.confirmed_by_creator = False
            state.confirmation_status = "not_confirmed"
            state.generation_status = "not_started"
            next_f = missing[0]
            state.current_stage = (
                "awaiting_title"
                if next_f == "story_title"
                else ("awaiting_style" if next_f == "visual_style" else "awaiting_context")
            )

        reply = extracted.natural_response.strip()
        if _looks_like_internal_analysis(reply):
            reply = _build_natural_fallback(state, missing, is_document=(input_source == "document"))

        state.last_assistant_question = reply
        state.updated_at = datetime.now(timezone.utc).isoformat()

        style_options = DEFAULT_STYLE_OPTIONS if extracted.requests_style_suggestions or (missing and missing[0] == "visual_style") else []

        return IntakeAnalysisResult(
            intent=extracted.intent,
            intake_state=state,
            missing_fields=missing,
            next_question_field=missing[0] if missing else None,
            ready_for_story_development=ready_for_story,
            needs_confirmation=needs_confirmation,
            assistant_message=reply,
            suggested_titles=state.suggested_titles if extracted.requests_title_suggestions else [],
            style_options=style_options,
        )
