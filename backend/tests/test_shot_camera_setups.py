"""One camera setup (framing + angle) per shot: rule helpers and pipeline guards."""

from __future__ import annotations

from app.api.v1.endpoints.ai_chat import SYSTEM_PROMPT, _split_camera_setups, _split_multi_frame_shots
from app.engines.production.engine import SHOT_SYSTEM_PROMPT, expand_camera_setups
from app.engines.production.schemas import CameraSpec, DialogueLineSpec, ProducedShotItem
from app.services.shot_rules import (
    CAMERA_SETUP_RULE_PROMPT,
    assign_frames_to_setups,
    split_angle_setups,
    split_framing_setups,
    split_movement_on_cuts,
)


# --------------------------------------------------------------------------- helpers


def test_single_framing_is_untouched() -> None:
    assert split_framing_setups("Low-Angle Wide Shot (WS)", "Slow crane upward") == ["Low-Angle Wide Shot (WS)"]
    assert split_framing_setups("Over-the-Shoulder (OTS)") == ["Over-the-Shoulder (OTS)"]
    assert split_framing_setups("Medium Close-Up (MCU)") == ["Medium Close-Up (MCU)"]


def test_compound_framing_splits_per_setup() -> None:
    assert split_framing_setups("Wide Shot (WS) to Close-Up (CU)", "Static") == ["Wide Shot (WS)", "Close-Up (CU)"]
    assert split_framing_setups("Medium Shot (MS) / Low-Angle Close-Up (CU)") == [
        "Medium Shot (MS)",
        "Low-Angle Close-Up (CU)",
    ]


def test_continuous_move_between_framings_is_one_setup() -> None:
    assert split_framing_setups("Wide Shot (WS) to Close-Up (CU)", "Slow push-in") == [
        "Wide Shot (WS) to Close-Up (CU)"
    ]


def test_prose_with_to_is_not_split() -> None:
    assert split_framing_setups("Close-Up on the hand to the mouth") == ["Close-Up on the hand to the mouth"]


def test_angle_field_splits() -> None:
    assert split_angle_setups("Low Angle to High Angle") == ["Low Angle", "High Angle"]
    assert split_angle_setups("Eye Level") == ["Eye Level"]


def test_movement_cut_markers() -> None:
    assert split_movement_on_cuts("Static, then cut to low-angle wide shot, slow crane up") == [
        "Static",
        "Low-angle wide shot, slow crane up",
    ]
    # A match cut INTO the shot is a transition, not an edit point inside it.
    assert split_movement_on_cuts("Static; match cut from the well rim in daylight to the same rim at dusk") == [
        "Static; match cut from the well rim in daylight to the same rim at dusk"
    ]
    assert split_movement_on_cuts("Rack focus from the stain to the persimmon") == [
        "Rack focus from the stain to the persimmon"
    ]


def test_assign_frames_to_setups() -> None:
    assert assign_frames_to_setups(["A", "B"], 2, "") == ["A", "B"]
    assert assign_frames_to_setups(["A"], 2, "") == ["A", "A"]
    assert assign_frames_to_setups(["A", "B", "C"], 2, "") == ["A", "B C"]


def test_rule_is_in_both_prompts() -> None:
    assert CAMERA_SETUP_RULE_PROMPT in SYSTEM_PROMPT
    assert CAMERA_SETUP_RULE_PROMPT in SHOT_SYSTEM_PROMPT


# --------------------------------------------------------------------------- chat pipeline


def _chat_shot(**overrides: object) -> dict:
    shot = {
        "shotId": "s1-sh1",
        "durationSeconds": 4,
        "framing": "Wide Shot (WS)",
        "cameraMovement": "Static",
        "characters": ["Ren Sato"],
        "location": "Village Square",
        "whatWeSee": "Ren paints a persimmon on the sign.",
        "dialogue": None,
        "emotion": "Focus",
        "sound": "Brush strokes.",
    }
    shot.update(overrides)
    return shot


def test_chat_angle_change_becomes_new_shot() -> None:
    scenes = [
        {
            "sceneId": "s1",
            "shots": [
                _chat_shot(
                    framing="Wide Shot (WS) to Low-Angle Close-Up (CU)",
                    whatWeSee="Ren stands at the stall. Ren looks up at the sign.",
                    dialogue={"speaker": "Ren Sato", "line": "Look!", "delivery": "Bright"},
                ),
                _chat_shot(framing="Medium Shot (MS)"),
            ],
        }
    ]
    out = _split_multi_frame_shots(_split_camera_setups(scenes))
    shots = out[0]["shots"]
    assert [s["framing"] for s in shots] == ["Wide Shot (WS)", "Low-Angle Close-Up (CU)", "Medium Shot (MS)"]
    assert [s["shotId"] for s in shots] == ["s1-sh1", "s1-sh2", "s1-sh3"]
    assert shots[0]["whatWeSee"].startswith("Ren stands at the stall")
    assert shots[1]["whatWeSee"].startswith("Ren looks up at the sign")
    # dialogue is kept on exactly one shot
    assert sum(1 for s in shots if s["dialogue"]) == 1


def test_chat_cut_in_movement_becomes_new_shot() -> None:
    scenes = [
        {
            "sceneId": "s2",
            "shots": [_chat_shot(cameraMovement="Static, then cut to high-angle wide shot, slow crane up")],
        }
    ]
    shots = _split_multi_frame_shots(_split_camera_setups(scenes))[0]["shots"]
    assert [(s["framing"], s["cameraMovement"]) for s in shots] == [
        ("Wide Shot (WS)", "Static"),
        ("High-angle wide shot", "Slow crane up"),
    ]


def test_chat_single_setup_shots_are_untouched() -> None:
    scenes = [{"sceneId": "s1", "shots": [_chat_shot(), _chat_shot(framing="Close-Up (CU)")]}]
    shots = _split_camera_setups(scenes)[0]["shots"]
    assert len(shots) == 2


# --------------------------------------------------------------------------- production pipeline


def _prod_shot(order: int, framing: str, angle: str, movement: str = "Static", dialogue: bool = False) -> ProducedShotItem:
    return ProducedShotItem(
        shot_id=f"S01_SH{order:02d}",
        shot_order=order,
        duration_seconds=4,
        framing=framing,
        camera=CameraSpec(angle=angle, movement=movement),
        characters=["Ren Sato"],
        location="Village Square",
        visual_description="Ren looks at the tree.",
        dialogue=[DialogueLineSpec(speaker="Ren Sato", exact_line="Look!", delivery="Bright")] if dialogue else [],
        emotion="Wonder",
        sound="Wind",
    )


def test_production_compound_angle_splits() -> None:
    out = expand_camera_setups(
        [
            _prod_shot(1, "Wide Shot (WS)", "Low Angle to High Angle", dialogue=True),
            _prod_shot(2, "Close-Up (CU)", "Eye Level"),
        ]
    )
    assert [(s.framing, s.camera.angle) for s in out] == [
        ("Wide Shot (WS)", "Low Angle"),
        ("Wide Shot (WS)", "High Angle"),
        ("Close-Up (CU)", "Eye Level"),
    ]
    assert [len(s.dialogue) for s in out] == [1, 0, 0]


def test_production_cut_in_movement_splits() -> None:
    out = expand_camera_setups([_prod_shot(1, "Medium Shot (MS)", "Eye Level", "Pan left, cut to close-up (CU)")])
    assert [(s.framing, s.camera.movement) for s in out] == [
        ("Medium Shot (MS)", "Pan left"),
        ("Close-up (CU)", "Static"),
    ]
