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
    settings = get_settings()
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

