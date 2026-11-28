"""Story intake must be satisfied before the automated story -> planner pipeline runs."""

import pytest

from app.api.v1.endpoints.chat import _should_auto_generate
from app.engines.story_intake import IntakeState
from app.engines.story_intake.engine import _is_generic_story_request
from app.engines.story_intake.schemas import IntakeAnalysisResult

FULL = {"story_title": "The Moonlight Guardian", "visual_style": "3D Pixar", "story_context": "A fox guards the forest."}


def _result(state: IntakeState, *, ready: bool = False) -> IntakeAnalysisResult:
    return IntakeAnalysisResult(
        intent="provide_details",
        intake_state=state,
        missing_fields=state.missing_fields(),
        next_question_field=None,
        ready_for_story_development=ready,
        needs_confirmation=state.is_complete() and not ready,
        assistant_message="ok",
    )


@pytest.mark.parametrize(
    "text",
    ["can you generate a story for me", "Write me a fun story please!", "make a story", "tell me a bedtime story for kids", ""],
)
def test_generic_requests_are_not_premises(text: str) -> None:
    assert _is_generic_story_request(text)


@pytest.mark.parametrize(
    "text",
    ["A brave little fox protects the forest at night", "The girl chased her dream.", "generate a story about a lost robot"],
)
def test_real_premises_are_kept(text: str) -> None:
    assert not _is_generic_story_request(text)


def test_incomplete_intake_never_generates() -> None:
    state = IntakeState(story_title="The Moonlight Guardian")
    assert not _should_auto_generate(IntakeState(), _result(state))


def test_all_fields_in_one_message_generates_immediately() -> None:
    assert _should_auto_generate(IntakeState(), _result(IntakeState(**FULL)))


def test_fields_collected_over_turns_wait_for_confirmation() -> None:
    previous = IntakeState(story_title="The Moonlight Guardian", visual_style="3D Pixar")
    assert not _should_auto_generate(previous, _result(IntakeState(**FULL)))
    assert _should_auto_generate(IntakeState(**FULL), _result(IntakeState(**FULL), ready=True))


def test_title_or_style_only_messages_are_not_premises() -> None:
    known = ("The Moonlight Guardian", "3D Pixar style animation")
    assert _is_generic_story_request("The title is The Moonlight Guardian", known_values=known)
    assert _is_generic_story_request("3D Pixar style animation", known_values=known)
    assert not _is_generic_story_request("A fox guards the forest", known_values=known)
