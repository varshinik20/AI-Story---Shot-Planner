import type { ShotPlanner } from '@/types/planner'

export const BOY_WHO_CRIED_WOLF_PLANNER: ShotPlanner = {
  id: 'planner_boy_who_cried_wolf',
  isApproved: false,
  overview: {
    filmTitle: 'The Boy Who Cried Wolf',
    logline:
      'Bored on a quiet hillside, a young shepherd stages a wolf attack for thrills—only to face silent village disbelief when a real predator emerges from the dusk.',
    totalScenes: 3,
    totalShots: 17,
    dialogueLines: 13,
    runningTimeSeconds: 73,
    videoFormat: '16:9 (1920x1080 HD)',
    frameRate: '24 fps',
    creatorsIntent:
      'A grounded, atmospheric fable rendered in warm-to-cold cinematic realism. Contrast golden afternoon boredom with stark twilight tension, using tight close-ups to track how careless deceit erodes community trust.',
  },
  characters: [
    {
      id: 'char_leo',
      name: 'Leo (The Shepherd Boy)',
      role: 'Protagonist',
      physicalAppearance:
        '11 years old, tousled sandy-brown hair, oversized wool vest over a linen tunic, weathered wooden crook, muddy boots.',
      personalityAndVoice:
        'Restless, imaginative, and craving attention; speaks with bright, quick cadence early on that cracks into raw panic by the final scene.',
    },
    {
      id: 'char_martha',
      name: 'Elder Martha',
      role: 'Village Elder',
      physicalAppearance:
        'Mid-60s, silver braid tucked under a woven shawl, sharp eyes lined with care, carries a carved ash walking cane.',
      personalityAndVoice:
        'Measured, observant, and protective of the village; speaks in calm, low-pitched authority that carries moral weight.',
    },
    {
      id: 'char_thomas',
      name: 'Thomas (The Blacksmith)',
      role: 'Supporting Villager',
      physicalAppearance:
        'Broad-shouldered man in his 40s, soot-smudged leather apron, rolled sleeves, thick forearms gripping a pitchfork.',
      personalityAndVoice:
        'Practical, loyal, and quick to act in crisis—but unforgiving once mocked; booming, gravelly baritone.',
    },
    {
      id: 'char_sarah',
      name: 'Sarah (The Baker)',
      role: 'Supporting Villager',
      physicalAppearance:
        'Early 30s, flour-dusted skirt and headscarf, rosy cheeks from the hearth, carrying a wooden bread peel when interrupted.',
      personalityAndVoice:
        'Warm-hearted yet weary from daily labor; brisk, expressive voice that turns flat and dismissive after the prank.',
    },
  ],
  locations: [
    {
      id: 'loc_pasture',
      name: 'Hillside Pasture',
      visualDescription:
        'A sweeping emerald slope dotted with limestone boulders and grazing sheep, overlooking a cluster of slate-roofed cottages in the valley below.',
    },
    {
      id: 'loc_village',
      name: 'Village Square',
      visualDescription:
        'Cobblestone courtyard flanked by stone hearths, a blacksmith forge glowing amber, and timber-framed houses connected by winding dirt paths.',
    },
    {
      id: 'loc_forest',
      name: 'Forest Edge',
      visualDescription:
        'Dense, ancient pine treeline bordering the upper pasture where long twilight shadows stretch across tall ferns and mist gathers close to the ground.',
    },
  ],
  scenes: [
    {
      sceneId: 'S01',
      sceneTitle: 'The Restless Watch',
      locations: ['Hillside Pasture'],
      timeOfDay: 'Late Afternoon',
      shots: [
        {
          shotId: 'S01_SH01',
          durationSeconds: 5,
          framing: 'Extreme Wide Shot (EWS)',
          cameraMovement: 'Slow Pan Right',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Golden afternoon sunlight washes over the hillside pasture. Sheep graze peacefully while Leo sits slumped against a boulder in the distance, tossing pebbles down the slope toward the quiet village below.',
          dialogue: null,
          emotion: 'Restlessness and isolation',
          sound: 'Gentle wind through tall grass, distant sheep bells, soft thud of pebbles.',
        },
        {
          shotId: 'S01_SH02',
          durationSeconds: 4,
          framing: 'Medium Close-Up (MCU)',
          cameraMovement: 'Static',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Leo rests his chin on his crook, staring blankly down at the village chimneys puffing thin trails of smoke.',
          dialogue: {
            speaker: 'Leo',
            line: 'Same hills. Same grass. Nothing ever happens up here.',
            delivery: 'Sighing, bored and under his breath',
          },
          emotion: 'Boredom and longing for excitement',
          sound: 'Soft breeze, quiet rustle of wool vest, faint rooster crow from the valley.',
        },
        {
          shotId: 'S01_SH03',
          durationSeconds: 4,
          framing: 'Close-Up (CU)',
          cameraMovement: 'Slow Push-In',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Leo’s eyes glance toward the dark pine treeline, then back down to the village square. A mischievous grin slowly forms across his face.',
          dialogue: {
            speaker: 'Leo',
            line: 'Wait... what if it does?',
            delivery: 'Whispered, playful spark of mischief',
          },
          emotion: 'Mischievous curiosity',
          sound: 'Subtle woodwind swell, crisp snap of a dry twig in Leo’s hand.',
        },
        {
          shotId: 'S01_SH04',
          durationSeconds: 5,
          framing: 'Medium Shot (MS)',
          cameraMovement: 'Tilt Up',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Leo leaps onto the tallest boulder, cups both hands around his mouth toward the valley, and leans forward dramatically.',
          dialogue: {
            speaker: 'Leo',
            line: 'Wolf! A wolf is after the sheep! Help!',
            delivery: 'Loud, theatrical, feigning terror',
          },
          emotion: 'Feigned panic masking thrill',
          sound: 'Leo’s shout echoing across the hillside, startled bleating of nearby sheep.',
        },
        {
          shotId: 'S01_SH05',
          durationSeconds: 4,
          framing: 'Wide Shot (WS)',
          cameraMovement: 'Static',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'From behind Leo’s silhouette on the ridge, tiny figures in the distant village square stop their chores and begin rushing toward the hillside path.',
          dialogue: null,
          emotion: 'Anticipation and smug triumph',
          sound: 'Distant clanging bell, faint muffled shouts rising from the valley.',
        },
      ],
    },
    {
      sceneId: 'S02',
      sceneTitle: 'The False Alarm',
      locations: ['Village Square', 'Hillside Pasture'],
      timeOfDay: 'Dusk',
      shots: [
        {
          shotId: 'S02_SH01',
          durationSeconds: 4,
          framing: 'Medium Wide Shot (MWS)',
          cameraMovement: 'Handheld Follow',
          characters: ['Thomas', 'Sarah', 'Elder Martha'],
          location: 'Village Square',
          whatWeSee:
            'Thomas drops his hammer beside the glowing forge and snatches a pitchfork while Sarah and Elder Martha hurry past the stone cottages onto the steep trail.',
          dialogue: {
            speaker: 'Thomas',
            line: 'Grab the pitchforks! Up the ridge!',
            delivery: 'Urgent, breathless bark',
          },
          emotion: 'Alarm and protective urgency',
          sound: 'Heavy boots pounding cobblestones, clatter of iron tools, hurried breathing.',
        },
        {
          shotId: 'S02_SH02',
          durationSeconds: 4,
          framing: 'Medium Shot (MS)',
          cameraMovement: 'Tracking Shot',
          characters: ['Elder Martha', 'Thomas', 'Sarah', 'Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'The villagers crest the hillside panting and scanning the empty meadow, finding the sheep calmly chewing grass while Leo sits grinning by the boulder.',
          dialogue: {
            speaker: 'Elder Martha',
            line: 'Where is it, boy? Are the flock safe?',
            delivery: 'Winded, sharp with concern',
          },
          emotion: 'Breathless worry turning to confusion',
          sound: 'Labored panting, rustling coats, calm sheep chewing.',
        },
        {
          shotId: 'S02_SH03',
          durationSeconds: 4,
          framing: 'Medium Close-Up (MCU)',
          cameraMovement: 'Static',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Leo doubles over laughing, slapping his knee and pointing at Thomas’s raised pitchfork.',
          dialogue: {
            speaker: 'Leo',
            line: "You should have seen your faces! There's no wolf!",
            delivery: 'Bright, mocking laughter',
          },
          emotion: 'Unapologetic amusement',
          sound: 'Boyish laughter cutting sharply across the quiet dusk air.',
        },
        {
          shotId: 'S02_SH04',
          durationSeconds: 4,
          framing: 'Close-Up (CU)',
          cameraMovement: 'Static',
          characters: ['Sarah'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Sarah lowers her bread peel, flour still smudged on her cheek as her expression hardens into exasperation.',
          dialogue: {
            speaker: 'Sarah',
            line: "This isn't a game, Leo. We dropped our work for you.",
            delivery: 'Clipped, frustrated and tired',
          },
          emotion: 'Frustration and resentment',
          sound: 'Sharp exhale, faint hiss of evening wind.',
        },
        {
          shotId: 'S02_SH05',
          durationSeconds: 5,
          framing: 'Over-the-Shoulder (OTS)',
          cameraMovement: 'Slow Push-In',
          characters: ['Elder Martha', 'Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Over Leo’s shoulder, Elder Martha leans gently on her cane, her gaze steady and unblinking as Thomas turns back toward the trail in disgust.',
          dialogue: {
            speaker: 'Elder Martha',
            line: 'A liar loses trust faster than a flock loses a lamb.',
            delivery: 'Quiet, firm warning',
          },
          emotion: 'Disappointment and solemn foreboding',
          sound: 'Low cello drone, crunch of boots turning away on gravel.',
        },
        {
          shotId: 'S02_SH06',
          durationSeconds: 4,
          framing: 'Medium Shot (MS)',
          cameraMovement: 'Pull-Back',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Leo shrugs off the warning as the villagers descend into the violet shadows below, tossing his crook lightly from hand to hand.',
          dialogue: {
            speaker: 'Leo',
            line: "They'll run up here again tomorrow. Watch.",
            delivery: 'Smug, muttered to himself',
          },
          emotion: 'Careless overconfidence',
          sound: 'Fading footsteps down the path, crickets beginning to chirp.',
        },
      ],
    },
    {
      sceneId: 'S03',
      sceneTitle: 'When Shadows Have Teeth',
      locations: ['Forest Edge', 'Hillside Pasture', 'Village Square'],
      timeOfDay: 'Twilight / Nightfall',
      shots: [
        {
          shotId: 'S03_SH01',
          durationSeconds: 4,
          framing: 'Extreme Close-Up (ECU)',
          cameraMovement: 'Slow Push-In',
          characters: ['Leo'],
          location: 'Forest Edge',
          whatWeSee:
            'Thick blue twilight blankets the pines. Between dark ferns, two pale amber eyes blink open and a low silhouette pads silently onto the pasture grass.',
          dialogue: null,
          emotion: 'Creeping dread',
          sound: 'Deep guttural snarl, snapping undergrowth, sudden silence from the crickets.',
        },
        {
          shotId: 'S03_SH02',
          durationSeconds: 5,
          framing: 'Close-Up (CU)',
          cameraMovement: 'Whip Pan',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Leo spins around as the sheep scatter wildly. Seeing the real wolf crouching near the rocks, his grin vanishes and he scrambles onto the boulder.',
          dialogue: {
            speaker: 'Leo',
            line: "No... that's not a shadow. Wolf! Real wolf! Please!",
            delivery: 'Cracking voice, desperate and breathless',
          },
          emotion: 'Sudden terror',
          sound: 'Panic-stricken bleating, frantic footsteps, high tense string tremolo.',
        },
        {
          shotId: 'S03_SH03',
          durationSeconds: 4,
          framing: 'Medium Shot (MS)',
          cameraMovement: 'Static',
          characters: ['Thomas', 'Elder Martha'],
          location: 'Village Square',
          whatWeSee:
            'In the warm lantern-lit village square, Thomas keeps hammering hot iron on the anvil without looking up while Elder Martha watches the dark ridge.',
          dialogue: {
            speaker: 'Thomas',
            line: "Hear that? He's playing his trick again.",
            delivery: 'Flat, dismissive scoff',
          },
          emotion: 'Cynical disbelief',
          sound: 'Rhythmic clang of hammer on anvil, crackling hearth fire, faint distant cries.',
        },
        {
          shotId: 'S03_SH04',
          durationSeconds: 4,
          framing: 'Medium Close-Up (MCU)',
          cameraMovement: 'Static',
          characters: ['Sarah'],
          location: 'Village Square',
          whatWeSee:
            'Sarah pulls a wooden shutter halfway closed across her bakery window, shaking her head in the amber light.',
          dialogue: {
            speaker: 'Sarah',
            line: "Don't waste your breath. Let him shout at the wind.",
            delivery: 'Cold, resolute indifference',
          },
          emotion: 'Hardened distrust',
          sound: 'Heavy thud of wooden shutter latching, muffled wind.',
        },
        {
          shotId: 'S03_SH05',
          durationSeconds: 5,
          framing: 'Wide Shot (WS)',
          cameraMovement: 'Crane Up',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'The camera rises above the moonlit hillside, isolating small Leo clutching his wooden crook on the boulder as the flock scatters toward the trees and no lanterns climb the path.',
          dialogue: {
            speaker: 'Leo',
            line: "Somebody... anyone! I wasn't lying this time!",
            delivery: 'Broken sob fading into the night',
          },
          emotion: 'Helpless regret and isolation',
          sound: 'Howling wind, distant wolf howl, lonely lingering piano chord.',
        },
        {
          shotId: 'S03_SH06',
          durationSeconds: 4,
          framing: 'Extreme Wide Shot (EWS)',
          cameraMovement: 'Static',
          characters: ['Leo'],
          location: 'Hillside Pasture',
          whatWeSee:
            'Wide tableau under cold starlight: warm golden windows glow peacefully in the unreachable village below, while the dark hillside sits empty save for Leo’s solitary silhouette.',
          dialogue: null,
          emotion: 'Somber moral finality',
          sound: 'Hollow night wind fading to silence.',
        },
      ],
    },
  ],
}
