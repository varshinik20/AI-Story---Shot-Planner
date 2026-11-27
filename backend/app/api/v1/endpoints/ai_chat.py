"""
AI Chat endpoint — routes user messages to OpenAI GPT-4o and returns
structured JSON that the frontend can render as chat messages + shot plans.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger("cinemind.ai_chat")
router = APIRouter(prefix="/ai", tags=["AI"])

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
- Keep `content` concise and cinematic — this is shown directly in the chat UI.
- Provide 3–4 `options` for every interview step (except when generating the planner).
- Generate at least 3 scenes with 3–6 shots each when producing the planner.
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
    system_context = (
        f"Current interview_step: {body.interview_step}\n"
        f"Story draft so far: {json.dumps(body.story_draft, ensure_ascii=False)}"
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
            max_completion_tokens=4096,
        )
    except OpenAIError as exc:
        logger.error("OpenAI API error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI error: {exc}",
        ) from exc

    raw = response.choices[0].message.content or "{}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Could not parse OpenAI JSON response: %s", raw[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned malformed JSON.",
        ) from exc

    return AIChatResponse(
        content=data.get("content", ""),
        next_step=data.get("next_step", body.interview_step),
        options=data.get("options"),
        planner=data.get("planner"),
        suggested_title=data.get("suggested_title"),
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
    except OpenAIError as exc:
        logger.error("OpenAI intake analyze error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI error: {exc}",
        ) from exc

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI intake analyzer returned malformed JSON.",
        ) from exc

    analysis_raw = data.get("analysis") if isinstance(data.get("analysis"), dict) else data
    conversation_raw = (
        data.get("conversation") if isinstance(data.get("conversation"), dict) else {}
    )

    extracted = analysis_raw.get("extracted_fields", {})
    missing = analysis_raw.get("missing_fields", [])
    assistant_msg = str(conversation_raw.get("assistant_message") or "").strip()

    if _looks_like_internal_analysis(assistant_msg):
        assistant_msg = _fallback_natural_message(extracted, missing, body.current_state)

    return IntakeAnalyzeResponse(
        analysis=IntakeAnalysisPayload(
            input_source=body.input_source,
            intent=analysis_raw.get("intent", "create_story"),
            extracted_fields=extracted,
            missing_fields=missing,
            next_action=analysis_raw.get("next_action", "ask_title"),
        ),
        conversation=IntakeConversationPayload(
            assistant_message=assistant_msg,
        ),
    )

