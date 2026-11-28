"""Regression & dynamic PDF verification tests matching the approved Shot Planner PDF specification."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.domain import (
    Character,
    CreativeIntent,
    CreatorApproval,
    Location,
    Scene,
    Shot,
    Story,
)
from app.db.models.project import Project


async def _seed_boy_who_cried_wolf(db_session: AsyncSession) -> Project:
    """Seed exact reference data matching Shot-Planner_The-Boy-Who-Cried-Wolf.pdf (3 scenes, 17 shots, 13 lines, 73s)."""
    project = Project(
        title="The Boy Who Cried Wolf",
        description=(
            "Bored on a quiet hillside, a young shepherd stages a wolf attack for thrills—"
            "only to face silent village disbelief when a real predator emerges from the dusk."
        ),
        status="completed",
    )
    db_session.add(project)
    await db_session.flush()

    dialogue_lines_in_story = [
        ("Leo", "Same hills. Same grass. Nothing ever happens up here.", "Sighing, bored and under his breath"),
        ("Leo", "Wolf! Wolf! Help! The wolf is attacking the flock!", "High-pitched, urgent scream cupping his hands"),
        ("Thomas", "Stay behind me, boy! Where did it go?", "Breathless, booming, scanning the ridge"),
        ("Elder Martha", "Catch your breath, Leo. Show us the tracks.", "Calm, protective, steady"),
        ("Leo", "You should have seen your faces! There isn't any wolf!", "Doubling over in breathless laughter"),
        ("Sarah", "Do you have any idea how far we climbed for your joke?", "Sharp, betrayed, pointing back toward the valley"),
        ("Leo", "Wolf! Wolf! Come quick, it's tearing through the sheep!", "Loud, theatrical bellow echoing down the valley"),
        ("Elder Martha", "False fear wears out real mercy, Leo. One day you'll cry out and no one will come.", "Low, measured warning with steady eyes"),
        ("Leo", "They'll run up here again tomorrow. Watch.", "Smug, muttered to himself"),
        ("Leo", "No... that's not a shadow. Wolf! Real wolf! Please!", "Cracking voice, desperate and breathless"),
        ("Thomas", "Hear that? He's playing his trick again.", "Flat, dismissive scoff"),
        ("Sarah", "Don't waste your breath. Let him shout at the wind.", "Cold, resolute indifference"),
        ("Leo", "Somebody... anyone! I wasn't lying this time!", "Broken sob fading into the night"),
    ]
    approved_text = (
        "On a golden afternoon hillside overlooking the village, Leo watched the sheep. "
        + " ".join(f'{spk} said, "{line}"' for spk, line, _ in dialogue_lines_in_story)
    )

    story = Story(
        project_id=project.id,
        title="The Boy Who Cried Wolf",
        visual_style="Warm-to-cold cinematic realism",
        premise=project.description or "",
        source_type="intake_confirmed",
        original_content=approved_text,
        working_content=approved_text,
        approved_content=approved_text,
        status="approved",
        structure_json={
            "logline": project.description,
            "central_theme": "Careless deceit erodes community trust.",
        },
    )
    intent = CreativeIntent(
        project_id=project.id,
        visual_style="Warm-to-cold cinematic realism",
        overall_mood="Bored golden afternoon escalating to stark twilight dread",
        pacing="Measured fable build-up with urgent panic cuts",
        lighting="Golden afternoon sunlight transitioning to violet dusk and cold blue nightfall",
        camera_preferences="Wide hillside landscapes contrasted with tight emotional close-ups",
        audience_experience="Family / timeless cautionary moral resonance",
        ending_tone="Somber moral finality",
        interview_answers={
            "production_format": "16:9 · 24 FPS",
            "overall_atmosphere": "Quiet pastoral hills hardening into indifferent twilight",
            "character_treatment": "Intimate close-ups tracking Leo's deceit turning to isolation",
            "intended_emotional_impact": "Sharp transition from playful mischief to haunting regret",
            "lighting_and_color": "Warm golden sunlight cooling into stark twilight blues",
            "desired_ending_experience": "Somber reflection on lost trust",
            "central_theme": "Careless deceit destroys credibility when crisis turns real",
        },
        is_complete=True,
    )
    characters = [
        Character(
            project_id=project.id,
            character_code="CHAR-001",
            name="Leo (The Shepherd Boy)",
            role="Protagonist",
            physical_appearance="11 years old, tousled sandy-brown hair, oversized wool vest over linen tunic, weathered wooden crook, muddy boots.",
            personality="Restless, imaginative, and craving attention.",
            voice_characteristics="Bright, quick cadence early on cracking into raw panic by the final scene.",
        ),
        Character(
            project_id=project.id,
            character_code="CHAR-002",
            name="Elder Martha",
            role="Village Elder",
            physical_appearance="Mid-60s, silver braid tucked under woven shawl, sharp eyes, carved ash walking cane.",
            personality="Measured, observant, protective.",
            voice_characteristics="Calm, low-pitched authority carrying moral weight.",
        ),
        Character(
            project_id=project.id,
            character_code="CHAR-003",
            name="Thomas (The Blacksmith)",
            role="Supporting Villager",
            physical_appearance="Broad-shouldered man in his 40s, soot-smudged leather apron, rolled sleeves, pitchfork.",
            personality="Practical, loyal, unforgiving once mocked.",
            voice_characteristics="Booming, gravelly baritone.",
        ),
        Character(
            project_id=project.id,
            character_code="CHAR-004",
            name="Sarah (The Baker)",
            role="Supporting Villager",
            physical_appearance="Early 30s, flour-dusted skirt and headscarf, rosy cheeks, wooden bread peel.",
            personality="Warm-hearted yet weary, turns dismissive after prank.",
            voice_characteristics="Brisk, expressive voice turning cold and resolute.",
        ),
    ]
    locations = [
        Location(
            project_id=project.id,
            location_code="LOC-001",
            name="Hillside Pasture",
            description="Sweeping emerald slope dotted with limestone boulders and grazing sheep overlooking cottages below.",
            time_of_day="Late Afternoon",
        ),
        Location(
            project_id=project.id,
            location_code="LOC-002",
            name="Village Square",
            description="Cobblestone courtyard flanked by stone hearths, blacksmith forge, and timber-framed houses.",
            time_of_day="Afternoon / Night",
        ),
        Location(
            project_id=project.id,
            location_code="LOC-003",
            name="Forest Edge",
            description="Dense ancient pine treeline bordering upper pasture where twilight shadows and mist gather.",
            time_of_day="Twilight",
        ),
    ]
    db_session.add_all([story, intent, *characters, *locations])
    await db_session.flush()

    scenes_spec = [
        (
            "S01", 1, "The Restless Watch", "Hillside Pasture", "Late Afternoon",
            "Leo grows bored tending sheep alone and cries wolf for the first time.",
            [
                ("S01_SH01", 5, "Extreme Wide Shot (EWS)", "Eye Level", "Slow Pan Right", ["Leo"], "Hillside Pasture", "Golden sunlight washes over pasture while Leo sits slumped tossing pebbles.", None, "Restlessness and isolation", "Gentle wind, distant sheep bells, pebble thuds."),
                ("S01_SH02", 4, "Medium Close-Up (MCU)", "Eye Level", "Static", ["Leo"], "Hillside Pasture", "Leo rests his chin on his crook staring down at village chimneys.", dialogue_lines_in_story[0], "Boredom and longing", "Soft breeze, wool rustle, distant rooster."),
                ("S01_SH03", 4, "Close-Up (CU)", "Eye Level", "Slow Push-In", ["Leo"], "Hillside Pasture", "A mischievous spark flashes across Leo's face looking toward the forest treeline.", None, "Mischievous impulse", "Faint rising flute motif, snapping twig."),
                ("S01_SH04", 5, "Wide Shot (WS)", "Low Angle", "Tilt Up", ["Leo"], "Hillside Pasture", "Leo scrambles onto a limestone boulder and cups his hands to shout.", dialogue_lines_in_story[1], "Feigned panic and thrill", "Echoing cries across valley, startled bleating."),
                ("S01_SH05", 4, "Tracking Shot (MS)", "Eye Level", "Handheld Follow", ["Thomas", "Sarah", "Elder Martha"], "Village Square", "Villagers drop tools and sprint uphill clutching pitchfork and bread peel.", None, "Urgency and concern", "Pounding footsteps, clattering bucket, panting."),
                ("S01_SH06", 4, "Two-Shot (MS)", "Eye Level", "Static", ["Thomas", "Elder Martha", "Leo"], "Hillside Pasture", "Thomas and Elder Martha crest the ridge breathing heavily beside calm sheep.", dialogue_lines_in_story[2], "Breathless alarm", "Heavy breathing, rattling tools."),
            ],
        ),
        (
            "S02", 2, "The False Alarm", "Hillside Pasture", "Dusk",
            "Villagers confront Leo's prank and return to warn him against deceiving them.",
            [
                ("S02_SH01", 4, "Close-Up (CU)", "Eye Level", "Static", ["Elder Martha", "Leo"], "Hillside Pasture", "Elder Martha catches her breath and examines the undisturbed grass.", dialogue_lines_in_story[3], "Measured suspicion", "Quiet hillside breeze."),
                ("S02_SH02", 4, "Medium Shot (MS)", "Low Angle", "Static", ["Leo"], "Hillside Pasture", "Leo bursts out laughing proudly atop the boulder.", dialogue_lines_in_story[4], "Gleeful mischief", "Bright laughter echoing, uneasy stillness."),
                ("S02_SH03", 4, "Close-Up (CU)", "Eye Level", "Static", ["Sarah"], "Hillside Pasture", "Sarah stares at Leo with reddened anger, holding her wooden peel.", dialogue_lines_in_story[5], "Betrayal and irritation", "Tense silence, sharp exhale."),
                ("S02_SH04", 5, "Wide Shot (WS)", "High Angle", "Crane Up", ["Leo", "Thomas", "Sarah"], "Hillside Pasture", "Later at dusk Leo repeats the false shout again before villagers turn away coldly.", dialogue_lines_in_story[6], "Reckless defiance", "Distant shouting, boots turning on gravel."),
                ("S02_SH05", 5, "Over-the-Shoulder (OTS)", "Eye Level", "Static", ["Elder Martha", "Leo"], "Hillside Pasture", "Elder Martha pauses on the path to deliver a solemn final warning.", dialogue_lines_in_story[7], "Solemn foreboding", "Low cello drone, gravel crunch."),
                ("S02_SH06", 4, "Medium Shot (MS)", "Eye Level", "Pull-Back", ["Leo"], "Hillside Pasture", "Leo shrugs off the warning tossing his wooden crook lightly.", dialogue_lines_in_story[8], "Careless overconfidence", "Fading footsteps, evening crickets."),
            ],
        ),
        (
            "S03", 3, "When Shadows Have Teeth", "Forest Edge, Hillside Pasture, Village Square", "Twilight / Nightfall",
            "A real wolf stalks the hillside while the village ignores Leo's genuine cries.",
            [
                ("S03_SH01", 4, "Extreme Close-Up (ECU)", "Low Angle", "Slow Push-In", ["Leo"], "Forest Edge", "Two pale amber eyes blink open between dark ferns as twilight blankets the pines.", None, "Creeping dread", "Deep guttural snarl, snapping undergrowth."),
                ("S03_SH02", 5, "Close-Up (CU)", "Eye Level", "Whip Pan", ["Leo"], "Hillside Pasture", "Leo spins around as sheep scatter wildly and scrambles onto the boulder.", dialogue_lines_in_story[9], "Sudden terror", "Panic-stricken bleating, frantic footsteps, string tremolo."),
                ("S03_SH03", 4, "Medium Shot (MS)", "Eye Level", "Static", ["Thomas", "Elder Martha"], "Village Square", "Thomas hammers hot iron in the square without looking up while Martha watches the ridge.", dialogue_lines_in_story[10], "Cynical disbelief", "Hammer clang on anvil, crackling hearth fire."),
                ("S03_SH04", 4, "Medium Close-Up (MCU)", "Eye Level", "Static", ["Sarah"], "Village Square", "Sarah pulls a wooden shutter halfway closed across her bakery window.", dialogue_lines_in_story[11], "Hardened distrust", "Heavy shutter latching, muffled wind."),
                ("S03_SH05", 5, "Wide Shot (WS)", "High Angle", "Crane Up", ["Leo"], "Hillside Pasture", "Camera rises above moonlit hillside isolating small Leo clutching his crook as sheep flee.", dialogue_lines_in_story[12], "Helpless regret", "Howling wind, distant wolf howl, lonely piano chord."),
                ("S03_SH06", 4, "Extreme Wide Shot (EWS)", "High Angle", "Static", ["Leo"], "Hillside Pasture", "Wide starlight tableau: warm village windows glow far below while the dark hillside sits isolated.", None, "Somber moral finality", "Hollow night wind fading to silence."),
            ],
        ),
    ]
    # Note: 6 + 6 + 6 = 18? Look carefully: 5+4+4+5+4+4 = 26s (6 shots); 4+4+4+5+5+4 = 26s (6 shots); 4+5+4+4+5+4 = 26s -> adjust Scene 1/2 to exact 17 shots & 73s!
    # Wait: S01 had 6 shots (26s? No, S01=5 shots if S01=5+4+4+5+4=22s, S02=6 shots 4+4+4+5+5+4=26s -> 22+26+25=73s!)
    # Remove extra S01_SH06 or keep exact 17 shots summing to 73s! Let's merge S01 to 5 shots (5+4+4+5+4 = 22s), S02 6 shots (25s with S02_SH05=4s), S03 6 shots (26s -> 22+25+26 = 73s) OR check total seconds:
    # 5+4+4+5+4 = 22 | 4+4+4+5+4+4 = 25 | 4+5+4+4+5+4 = 26 => 22 + 25 + 26 = 73 seconds & 5 + 6 + 6 = 17 shots & 13 dialogue lines!
    scenes_spec[0][6].pop()  # S01 -> 5 shots (keeps dialogue[0], dialogue[1], plus Thomas's line moves cleanly if needed -> wait!)
    # Better: keep Thomas's line dialogue[2] inside S01_SH05 so ALL 13 dialogue lines are preserved!
    s1_sh5 = scenes_spec[0][6][4]
    scenes_spec[0][6][4] = (
        "S01_SH05", 4, s1_sh5[2], s1_sh5[3], s1_sh5[4], ["Thomas", "Sarah", "Elder Martha", "Leo"], "Hillside Pasture",
        "Villagers rush up the hillside to reach Leo among calm sheep.", dialogue_lines_in_story[2], s1_sh5[9], s1_sh5[10]
    )
    # Trim S02_SH05 from 5s to 4s so 22 + 25 + 26 = 73 seconds exact!
    s2_sh5 = scenes_spec[1][6][4]
    scenes_spec[1][6][4] = (s2_sh5[0], 4, *s2_sh5[2:])

    for sc_id, order, title, loc_str, tod, summary, shots_list in scenes_spec:
        sc = Scene(
            project_id=project.id,
            scene_id=sc_id,
            scene_order=order,
            title=title,
            location=loc_str,
            time_of_day=tod,
            summary=summary,
            event_ids=[f"E{order:03d}"],
            is_approved=True,
            shots_generated=True,
        )
        db_session.add(sc)
        await db_session.flush()
        for sh_idx, (sid, dur, frm, ang, mov, chars, loc_name, desc, dlg, emo, snd) in enumerate(shots_list, start=1):
            db_session.add(
                Shot(
                    project_id=project.id,
                    scene_uuid=sc.id,
                    shot_id=sid,
                    shot_order=sh_idx,
                    duration_seconds=dur,
                    framing=frm,
                    camera={"angle": ang, "movement": mov},
                    characters=chars,
                    location=loc_name,
                    visual_description=desc,
                    dialogue=[{"speaker": dlg[0], "exact_line": dlg[1], "delivery": dlg[2]}] if dlg else [],
                    emotion=emo,
                    sound=snd,
                )
            )

    db_session.add(
        CreatorApproval(
            project_id=project.id,
            gate="final_shot_plan",
            target_ref="3 scenes / 17 shots",
            approved=True,
        )
    )
    await db_session.commit()
    return project


@pytest.mark.asyncio
async def test_reference_boy_who_cried_wolf_pdf_regression(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Section 11 regression check: exact reference stats, sections, 8 columns, dialogue, and layout."""
    project = await _seed_boy_who_cried_wolf(db_session)

    val_res = await client.get(f"/api/v1/planner/validate-pdf/{project.id}")
    assert val_res.status_code == 200
    v = val_res.json()
    assert v["valid"] is True
    assert v["scene_count"] == 3
    assert v["shot_count"] == 17
    assert v["dialogue_lines_count"] == 13
    assert v["total_runtime_seconds"] == 73
    assert v["character_count"] == 4
    assert v["location_count"] == 3

    pdf_res = await client.get(f"/api/v1/planner/export/{project.id}")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"

    reader = PdfReader(io.BytesIO(pdf_res.content))
    pages_text = [p.extract_text() or "" for p in reader.pages]
    full_text = "\n".join(pages_text)
    normalized_full = " ".join(full_text.split())

    # Page 1 overview hierarchy
    assert "SHOT PLANNER" in pages_text[0]
    assert "The Boy Who Cried Wolf" in pages_text[0]
    assert "3 SCENES | 17 SHOTS | 13 DIALOGUE LINES | 73 SECONDS | 16:9 · 24 FPS" in " ".join(pages_text[0].split())
    assert "CREATOR'S INTENT" in pages_text[0]
    for label in (
        "Visual style",
        "Overall atmosphere",
        "Character treatment",
        "Intended emotional impact",
        "Lighting and colour direction",
        "Desired ending experience",
        "Central theme",
    ):
        assert label in pages_text[0]

    assert "CHARACTERS" in full_text
    for ch_name in ("Leo (The Shepherd Boy)", "Elder Martha", "Thomas (The Blacksmith)", "Sarah (The Baker)"):
        assert ch_name in full_text

    assert "LOCATIONS" in full_text
    for loc_name in ("Hillside Pasture", "Village Square", "Forest Edge"):
        assert loc_name in full_text

    # 8 exact shot columns
    for col_name in (
        "SHOT",
        "SEC",
        "FRAMING · CAMERA",
        "CHARACTERS · LOCATION",
        "WHAT WE SEE",
        "DIALOGUE",
        "EMOTION",
        "SOUND",
    ):
        assert col_name in full_text

    # Scene sections & shot IDs + exact dialogue & explicit None
    assert "S01 · The Restless Watch" in normalized_full
    assert "S02 · The False Alarm" in normalized_full
    assert "S03 · When Shadows Have Teeth" in normalized_full
    assert "S01_SH01" in normalized_full
    assert "S03_SH06" in normalized_full
    assert "Same hills. Same grass. Nothing ever happens up here." in normalized_full
    assert "Somebody... anyone! I wasn't lying this time!" in normalized_full
    assert "None" in normalized_full


@pytest.mark.asyncio
async def test_dynamic_different_story_pdf_and_validator_rejection(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Different story generates a completely dynamic PDF; invalid data raises 422 instead of silent export."""
    project = Project(
        title="Lanterns Over Kyoto",
        description="Two estranged sisters launch glowing paper lanterns down the Kamo River at midnight.",
        status="completed",
    )
    db_session.add(project)
    await db_session.flush()

    approved_text = (
        "Mina knelt beside the stone step as Yuki lit the paper wick. "
        'Yuki whispered, "May the current carry it farther than we could walk."'
    )
    story = Story(
        project_id=project.id,
        title="Lanterns Over Kyoto",
        visual_style="Ghibli-inspired Nocturnal Watercolor",
        premise=project.description or "",
        source_type="intake_confirmed",
        original_content=approved_text,
        working_content=approved_text,
        approved_content=approved_text,
        status="approved",
    )
    intent = CreativeIntent(
        project_id=project.id,
        visual_style="Ghibli-inspired Nocturnal Watercolor",
        overall_mood="Poetic and bittersweet",
        pacing="Slow gentle contemplation",
        lighting="Warm amber candle glow against indigo river reflections",
        camera_preferences="Smooth gliding water-level tracking shots",
        audience_experience="Quiet emotional catharsis",
        ending_tone="Hopeful reconciliation",
        is_complete=True,
    )
    c1 = Character(
        project_id=project.id, character_code="CHAR-001", name="Mina", role="Protagonist",
        physical_appearance="Dark indigo haori, tied hair", personality="Guarded", voice_characteristics="Quiet",
    )
    c2 = Character(
        project_id=project.id, character_code="CHAR-002", name="Yuki", role="Deuteragonist",
        physical_appearance="Mustard knit shawl", personality="Warm", voice_characteristics="Soft whisper",
    )
    l1 = Location(project_id=project.id, location_code="LOC-001", name="Kamo Riverbank", description="Wet stone steps beside flowing black water.")
    l2 = Location(project_id=project.id, location_code="LOC-002", name="Wooden Bridge", description="Old cedar bridge draped in mist.")
    sc1 = Scene(
        project_id=project.id, scene_id="S01", scene_order=1, title="Lighting the Paper Boat",
        location="Kamo Riverbank", time_of_day="Midnight", summary="Sisters light the lantern.",
        event_ids=["E001"], is_approved=True, shots_generated=True,
    )
    sc2 = Scene(
        project_id=project.id, scene_id="S02", scene_order=2, title="Drifting Under the Arch",
        location="Wooden Bridge", time_of_day="Midnight", summary="Lantern floats past the cedar bridge.",
        event_ids=["E002"], is_approved=True, shots_generated=True,
    )
    db_session.add_all([story, intent, c1, c2, l1, l2, sc1, sc2])
    await db_session.flush()

    sh1 = Shot(
        project_id=project.id, scene_uuid=sc1.id, shot_id="S01_SH01", shot_order=1,
        duration_seconds=5, framing="Medium Shot (MS)", camera={"angle": "Eye Level", "movement": "Slow Push-In"},
        characters=["Mina", "Yuki"], location="Kamo Riverbank",
        visual_description="Candle flame catches inside folded rice paper above dark water.",
        dialogue=[{"speaker": "Yuki", "exact_line": "May the current carry it farther than we could walk.", "delivery": "Soft whisper"}],
        emotion="Yearning", sound="Gentle river ripples, match strike.",
    )
    sh2 = Shot(
        project_id=project.id, scene_uuid=sc2.id, shot_id="S02_SH01", shot_order=1,
        duration_seconds=6, framing="Wide Shot (WS)", camera={"angle": "Low Angle", "movement": "Tracking Shot"},
        characters=["Mina"], location="Wooden Bridge",
        visual_description="The glowing lantern glides silently beneath cedar pilings.",
        dialogue=[], emotion="Peaceful release", sound="Water lapping cedar pilings.",
    )
    db_session.add_all([sh1, sh2, CreatorApproval(project_id=project.id, gate="final_shot_plan", target_ref="2/2", approved=True)])
    await db_session.commit()

    res = await client.get(f"/api/v1/planner/export/{project.id}")
    assert res.status_code == 200
    text = " ".join("\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(res.content)).pages).split())
    assert "Lanterns Over Kyoto" in text
    assert "2 SCENES | 2 SHOTS | 1 DIALOGUE LINE | 11 SECONDS" in text
    assert "The Boy Who Cried Wolf" not in text
    assert "May the current carry it farther than we could walk." in text

    # Now mutate shot to invent ungrounded dialogue -> validator must reject with 422!
    sh2.dialogue = [{"speaker": "Mina", "exact_line": "This line never existed in the story!", "delivery": "Loud"}]
    await db_session.commit()
    bad_res = await client.get(f"/api/v1/planner/export/{project.id}")
    assert bad_res.status_code == 422
    assert "PDF_VALIDATION_FAILED" in bad_res.text
