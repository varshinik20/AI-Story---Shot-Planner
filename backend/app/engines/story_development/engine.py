"""Story Development Engine: collaborative story expansion, versioning, and creator-approved edits."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.db.models.conversation import Conversation
from app.db.models.domain import Story, StorySuggestion, StoryVersion
from app.engines.story_development.schemas import (
    LLMStoryDevelopmentPayload,
    StoryDetailResponse,
    StorySuggestionOut,
    StoryVersionOut,
)
from app.services.llm_service import LLMService

DEVELOP_SYSTEM_PROMPT = """You are CINEMIND's Story Development Partner.
Develop the creator's confirmed story premise into a vivid, film-ready complete narrative with a clear beginning, middle, and ending.

CRITICAL RULES:
1. STRICTLY retain every core premise detail, action, character, and plot event provided by the creator. Never replace or omit key events (for example, if the premise states a girl runs toward a cliff edge and falls down, that action MUST happen clearly in the narrative).
2. If the creator provided uploaded story text and preserve_original_text=true, refine structure minimally without rewriting their prose or inventing new dialogue.
3. Do NOT invent spoken dialogue lines unless dialogue already exists in the input or the instruction specifically asks for spoken lines. Visual action and sensory storytelling are preferred when no dialogue is supplied.
4. Provide 2 to 3 targeted, optional improvement suggestions (pacing, sensory atmosphere, emotional beat, or dramatic tension) where `original_passage` is an EXACT substring of `developed_story` so the creator can accept or reject each suggestion cleanly.

Return strict JSON matching the schema."""


class StoryDevelopmentEngine:
    """Manages collaborative drafting, inline suggestions, versions, and creator approval."""

    def __init__(self, session: AsyncSession, llm_service: LLMService) -> None:
        self.session = session
        self.llm = llm_service

    async def get_story_detail(self, story_id: uuid.UUID) -> StoryDetailResponse:
        story = (await self.session.execute(select(Story).where(Story.id == story_id))).scalar_one_or_none()
        if story is None:
            raise NotFoundError("Story not found.", code="STORY_NOT_FOUND")
        return await self._serialize_story(story)

    async def _serialize_story(self, story: Story) -> StoryDetailResponse:
        versions = (
            await self.session.execute(
                select(StoryVersion)
                .where(StoryVersion.story_id == story.id)
                .order_by(StoryVersion.version_number.asc())
            )
        ).scalars().all()
        suggestions = (
            await self.session.execute(
                select(StorySuggestion)
                .where(StorySuggestion.story_id == story.id)
                .order_by(StorySuggestion.created_at.asc())
            )
        ).scalars().all()

        return StoryDetailResponse(
            id=story.id,
            project_id=story.project_id,
            conversation_id=story.conversation_id,
            title=story.title,
            visual_style=story.visual_style,
            premise=story.premise,
            source_type=story.source_type,
            original_content=story.original_content,
            working_content=story.working_content,
            approved_content=story.approved_content,
            status=story.status,
            structure_json=story.structure_json,
            versions=[
                StoryVersionOut(
                    id=v.id,
                    story_id=v.story_id,
                    version_number=v.version_number,
                    label=v.label,
                    content=v.content,
                    is_approved=v.is_approved,
                )
                for v in versions
            ],
            suggestions=[
                StorySuggestionOut(
                    id=s.id,
                    story_id=s.story_id,
                    section_title=s.section_title,
                    original_passage=s.original_passage,
                    suggested_passage=s.suggested_passage,
                    explanation=s.explanation,
                    status=s.status,
                )
                for s in suggestions
            ],
        )

    async def _next_version_number(self, story_id: uuid.UUID) -> int:
        current = (
            await self.session.execute(
                select(func.coalesce(func.max(StoryVersion.version_number), 0)).where(
                    StoryVersion.story_id == story.id if False else StoryVersion.story_id == story_id
                )
            )
        ).scalar_one()
        return int(current) + 1

    async def develop_story(
        self,
        *,
        story_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        instruction: str | None = None,
        preserve_original_text: bool = False,
    ) -> StoryDetailResponse:
        story: Story | None = None
        if story_id is not None:
            story = (await self.session.execute(select(Story).where(Story.id == story_id))).scalar_one_or_none()
        elif project_id is not None:
            story = (
                await self.session.execute(
                    select(Story).where(Story.project_id == project_id).order_by(Story.created_at.desc())
                )
            ).scalars().first()
        if story is None:
            raise NotFoundError("No story found to develop for this project.", code="STORY_NOT_FOUND")

        existing_versions_count = (
            await self.session.execute(
                select(func.count()).select_from(StoryVersion).where(StoryVersion.story_id == story.id)
            )
        ).scalar_one()
        if existing_versions_count == 0:
            self.session.add(
                StoryVersion(
                    story_id=story.id,
                    version_number=1,
                    label="original",
                    content=story.original_content,
                    is_approved=False,
                )
            )
            await self.session.flush()

        prompt = (
            f"Story Title: {story.title}\n"
            f"Visual Style: {story.visual_style or 'Realistic Cinematic Film'}\n"
            f"Preserve original wording closely: {preserve_original_text}\n"
            f"Original / Current Working Story:\n{story.working_content}\n"
        )
        if instruction:
            prompt += f"\nCreator instruction for this draft: {instruction}\n"
        prompt += (
            "\nReturn strict JSON with keys: developed_story, beginning_summary, middle_summary, "
            "ending_summary, dialogue_present, suggestions (each with section_title, original_passage, "
            "suggested_passage, explanation)."
        )

        payload, _ = await self.llm.generate_json(
            messages=[
                {"role": "system", "content": DEVELOP_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            schema_model=LLMStoryDevelopmentPayload,
            engine="story_development",
            operation="develop_story",
            project_id=story.project_id,
            temperature=0.5,
            max_tokens=2200,
        )

        if preserve_original_text and story.source_type == "uploaded":
            story.working_content = story.original_content
        else:
            story.working_content = payload.developed_story.strip()

        story.structure_json = {
            **(story.structure_json or {}),
            "beginning": payload.beginning_summary,
            "middle": payload.middle_summary,
            "ending": payload.ending_summary,
            "dialogue_present": payload.dialogue_present,
        }
        story.status = "developing"

        next_num = await self._next_version_number(story.id)
        self.session.add(
            StoryVersion(
                story_id=story.id,
                version_number=next_num,
                label="draft",
                content=story.working_content,
                is_approved=False,
            )
        )

        # Replace previous pending suggestions while retaining historical accepted/rejected decisions
        await self.session.execute(
            delete(StorySuggestion).where(
                StorySuggestion.story_id == story.id,
                StorySuggestion.status == "pending",
            )
        )
        for item in payload.suggestions:
            self.session.add(
                StorySuggestion(
                    story_id=story.id,
                    section_title=item.section_title.strip(),
                    original_passage=item.original_passage.strip(),
                    suggested_passage=item.suggested_passage.strip(),
                    explanation=item.explanation.strip(),
                    status="pending",
                )
            )

        if story.conversation_id is not None:
            conv = (
                await self.session.execute(select(Conversation).where(Conversation.id == story.conversation_id))
            ).scalar_one_or_none()
            if conv is not None:
                conv.workflow_stage = "story_development"

        await self.session.commit()
        return await self._serialize_story(story)

    async def decide_suggestion(
        self,
        *,
        suggestion_id: uuid.UUID,
        decision: str,
        edited_text: str | None = None,
    ) -> StoryDetailResponse:
        suggestion = (
            await self.session.execute(select(StorySuggestion).where(StorySuggestion.id == suggestion_id))
        ).scalar_one_or_none()
        if suggestion is None:
            raise NotFoundError("Story suggestion not found.", code="SUGGESTION_NOT_FOUND")

        story = (
            await self.session.execute(select(Story).where(Story.id == suggestion.story_id))
        ).scalar_one_or_none()
        if story is None:
            raise NotFoundError("Associated story not found.", code="STORY_NOT_FOUND")

        if decision == "accept":
            replacement = (edited_text or suggestion.suggested_passage).strip()
            if suggestion.original_passage in story.working_content:
                story.working_content = story.working_content.replace(
                    suggestion.original_passage, replacement, 1
                )
            else:
                story.working_content = f"{story.working_content.rstrip()}\n\n{replacement}"
            suggestion.status = "accepted"
            suggestion.decided_at = datetime.now(timezone.utc)
            next_num = await self._next_version_number(story.id)
            self.session.add(
                StoryVersion(
                    story_id=story.id,
                    version_number=next_num,
                    label="edited",
                    content=story.working_content,
                    is_approved=False,
                )
            )
        elif decision == "reject":
            suggestion.status = "rejected"
            suggestion.decided_at = datetime.now(timezone.utc)
        else:
            raise BadRequestError("Decision must be 'accept' or 'reject'.", code="INVALID_DECISION")

        await self.session.commit()
        return await self._serialize_story(story)

    async def approve_story(
        self,
        *,
        story_id: uuid.UUID,
        edited_content: str | None = None,
    ) -> StoryDetailResponse:
        story = (await self.session.execute(select(Story).where(Story.id == story_id))).scalar_one_or_none()
        if story is None:
            raise NotFoundError("Story not found.", code="STORY_NOT_FOUND")

        if edited_content is not None and edited_content.strip():
            story.working_content = edited_content.strip()

        if not story.working_content.strip():
            raise BadRequestError("Cannot approve an empty story.", code="EMPTY_STORY")

        story.approved_content = story.working_content
        story.status = "approved"
        next_num = await self._next_version_number(story.id)
        self.session.add(
            StoryVersion(
                story_id=story.id,
                version_number=next_num,
                label="approved",
                content=story.approved_content,
                is_approved=True,
            )
        )

        if story.conversation_id is not None:
            conv = (
                await self.session.execute(select(Conversation).where(Conversation.id == story.conversation_id))
            ).scalar_one_or_none()
            if conv is not None:
                conv.workflow_stage = "intent_interview"

        await self.session.commit()
        return await self._serialize_story(story)
