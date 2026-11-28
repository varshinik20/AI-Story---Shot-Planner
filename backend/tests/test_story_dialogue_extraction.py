"""Deterministic extraction of verbatim story dialogue used to ground shot generation."""

from app.engines.production.engine import _normalize_dialogue_against_story, extract_story_dialogue

STORY = (
    "CLIMAX — Fern picks her way along the mill's low stone lip. Above her, Pip calls, “Fern?”\n\n"
    '"Keep ringing," she says. "I can\'t see the steps."\n\n'
    "Pip hands Fern a cup. “For the guardian,” he says. “Fern?”"
)


def test_extracts_each_line_once_in_story_order_with_context() -> None:
    lines = extract_story_dialogue(STORY)
    assert [d["exact_line"] for d in lines] == ["Fern?", "Keep ringing", "I can't see the steps.", "For the guardian"]
    assert "Pip calls" in lines[0]["context"]
    assert "he says" in lines[3]["context"]


def test_no_dialogue_returns_empty_list() -> None:
    assert extract_story_dialogue("A silent fox runs through the forest at night.") == []
    assert extract_story_dialogue("") == []


def test_extracted_lines_pass_the_grounding_guard() -> None:
    items = [{"speaker": "x", "exact_line": d["exact_line"], "delivery": "y"} for d in extract_story_dialogue(STORY)]
    assert _normalize_dialogue_against_story(items, STORY) == items
