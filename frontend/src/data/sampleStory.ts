import type { ShotPlanner } from '@/types/planner'
import type { StoryDraftState, StoryImprovementSuggestion } from '@/types/story'

export const SHADOW_SUGGESTIONS: StoryImprovementSuggestion[] = [
  {
    id: 'sug_shadow_1',
    sectionTitle: 'Opening Hook & Sensory Grounding',
    originalSegment:
      'Maya walked home from school and noticed her shadow did not match her steps on the sidewalk.',
    suggestedImprovement:
      'Under the flickering sodium streetlight on Elm Avenue, Maya froze mid-stride—her shadow kept walking three paces ahead, turning its head back to check if she was still watching.',
    explanation:
      'Anchoring the reveal in concrete lighting and an unmistakable physical discrepancy builds immediate cinematic tension for Scene 1.',
    status: 'pending',
  },
  {
    id: 'sug_shadow_2',
    sectionTitle: 'Emotional Stakes & Climax Beat',
    originalSegment:
      'She tried to run away from the shadow inside her bedroom, feeling very scared.',
    suggestedImprovement:
      'Maya slammed every lamp switch on in her bedroom, flooding the walls with harsh white light—only to watch her shadow peel softly off the floorboards like wet ink, holding out her lost childhood locket.',
    explanation:
      'Replacing an abstract feeling ("very scared") with a visual action and a concrete prop gives the camera something unforgettable to shoot.',
    status: 'pending',
  },
]

export function generateCustomShotPlanner(draft: StoryDraftState): ShotPlanner {
  const title = draft.title || 'The Shadow Within'
  const style = draft.visualStyle || 'Dark fantasy'
  const mood = draft.mood || 'Suspenseful and intimate'
  const motive = draft.shadowMotive || 'Reveal a hidden truth'
  const ending = draft.endingIntention || 'Bittersweet revelation'

  const baseSegments =
    draft.segments.length > 0
      ? draft.segments[0]
      : 'A young girl discovers her shadow moves independently, leading her to an unspoken family secret.'

  return {
    id: `planner_${Date.now().toString(36)}`,
    isApproved: false,
    overview: {
      filmTitle: title,
      logline: baseSegments,
      totalScenes: 3,
      totalShots: 9,
      dialogueLines: 6,
      runningTimeSeconds: 41,
      videoFormat: '16:9 (1920x1080 HD)',
      frameRate: '24 fps',
      creatorsIntent: `${style} aesthetic with a ${mood.toLowerCase()} tone. Central dynamic: the shadow seeks to ${motive.toLowerCase()}, building toward a ${ending.toLowerCase()}.`,
    },
    characters: [
      {
        id: 'char_maya',
        name: 'Maya',
        role: 'Protagonist',
        physicalAppearance:
          '16 years old, oversized charcoal coat, dark tousled hair, pale face lit by streetlamps and desk lamps.',
        personalityAndVoice:
          'Guarded, perceptive, quietly determined; speaks in hushed, measured phrases.',
      },
      {
        id: 'char_shadow',
        name: 'The Living Shadow',
        role: 'Supernatural Counterpart',
        physicalAppearance:
          'An elongated silhouette stretched across walls and pavement, edges subtly rippling like ink in water.',
        personalityAndVoice:
          'Silent yet expressive through posture and gesture; communicates through pointed stillness and light-play.',
      },
    ],
    locations: [
      {
        id: 'loc_elm',
        name: 'Elm Avenue Underpass',
        visualDescription:
          'Wet asphalt reflecting amber sodium streetlights beneath a quiet stone railway bridge.',
      },
      {
        id: 'loc_bedroom',
        name: "Maya's Attic Bedroom",
        visualDescription:
          'Slanted timber ceiling, tall dusty mirror, brass desk lamp casting sharp geometric shadows across faded wallpaper.',
      },
    ],
    scenes: [
      {
        sceneId: 'S01',
        sceneTitle: 'Out of Step',
        locations: ['Elm Avenue Underpass'],
        timeOfDay: 'Night',
        shots: [
          {
            shotId: 'S01_SH01',
            durationSeconds: 5,
            framing: 'Wide Shot (WS)',
            cameraMovement: 'Tracking Shot',
            characters: ['Maya', 'The Living Shadow'],
            location: 'Elm Avenue Underpass',
            whatWeSee:
              'Maya walks briskly under amber streetlights. On the wet pavement, her long shadow lags behind and suddenly raises a hand toward a shuttered storefront.',
            dialogue: null,
            emotion: 'Quiet unease',
            sound: 'Distant traffic hum, steady footsteps on damp pavement.',
          },
          {
            shotId: 'S01_SH02',
            durationSeconds: 4,
            framing: 'Close-Up (CU)',
            cameraMovement: 'Static',
            characters: ['Maya'],
            location: 'Elm Avenue Underpass',
            whatWeSee:
              'Maya stops dead, staring down at the asphalt as her breath forms a thin cloud in the chill air.',
            dialogue: {
              speaker: 'Maya',
              line: "No... that isn't the light playing tricks.",
              delivery: 'Hushed, breathless whisper',
            },
            emotion: 'Disbelief',
            sound: 'Buzz of faulty streetlight, quickening heartbeat.',
          },
          {
            shotId: 'S01_SH03',
            durationSeconds: 5,
            framing: 'Point of View (POV)',
            cameraMovement: 'Tilt Down',
            characters: ['The Living Shadow'],
            location: 'Elm Avenue Underpass',
            whatWeSee:
              'Looking down at the concrete: Maya stands perfectly still, yet her shadow steps sideways and points toward the uphill lane leading home.',
            dialogue: null,
            emotion: 'Uncanny fascination',
            sound: 'Low resonant cello swell.',
          },
        ],
      },
      {
        sceneId: 'S02',
        sceneTitle: 'Cornered by Light',
        locations: ["Maya's Attic Bedroom"],
        timeOfDay: 'Late Night',
        shots: [
          {
            shotId: 'S02_SH01',
            durationSeconds: 4,
            framing: 'Medium Shot (MS)',
            cameraMovement: 'Handheld Follow',
            characters: ['Maya'],
            location: "Maya's Attic Bedroom",
            whatWeSee:
              'Maya bursts into her attic room and flicks on every lamp switch, trying to erase every dark corner.',
            dialogue: {
              speaker: 'Maya',
              line: 'Stay back. Whatever you are, stay out of my room!',
              delivery: 'Trembling yet defiant',
            },
            emotion: 'Defensive fear',
            sound: 'Rapid clicks of light switches, heavy door latch.',
          },
          {
            shotId: 'S02_SH02',
            durationSeconds: 5,
            framing: 'Medium Close-Up (MCU)',
            cameraMovement: 'Slow Push-In',
            characters: ['The Living Shadow'],
            location: "Maya's Attic Bedroom",
            whatWeSee:
              'Against the bright wallpaper, the shadow refuses to vanish—stretching toward the dusty dresser mirror and tapping the bottom drawer.',
            dialogue: {
              speaker: 'Maya',
              line: "Wait... you aren't chasing me. You're showing me something.",
              delivery: 'Soft realization',
            },
            emotion: 'Fear softening into curiosity',
            sound: 'Subtle glass chime, ticking wall clock.',
          },
          {
            shotId: 'S02_SH03',
            durationSeconds: 4,
            framing: 'Close-Up (CU)',
            cameraMovement: 'Static',
            characters: ['Maya'],
            location: "Maya's Attic Bedroom",
            whatWeSee:
              'Maya kneels, slides open the false bottom of the drawer, and lifts out a tarnished silver locket wrapped in an old letter.',
            dialogue: {
              speaker: 'Maya',
              line: "Why did Mom hide this away?",
              delivery: 'Quiet wonder',
            },
            emotion: 'Awe and vulnerability',
            sound: 'Creak of old wood, rustle of folded parchment.',
          },
        ],
      },
      {
        sceneId: 'S03',
        sceneTitle: 'Two Halves',
        locations: ["Maya's Attic Bedroom"],
        timeOfDay: 'Pre-Dawn',
        shots: [
          {
            shotId: 'S03_SH01',
            durationSeconds: 5,
            framing: 'Two-Shot',
            cameraMovement: 'Slow Pan Left',
            characters: ['Maya', 'The Living Shadow'],
            location: "Maya's Attic Bedroom",
            whatWeSee:
              'Blue pre-dawn light filters through the skylight. Maya clutches the opened locket while her shadow gently aligns itself directly beneath her shoulders once more.',
            dialogue: {
              speaker: 'Maya',
              line: "You were never trying to take my place. You just wanted me to remember.",
              delivery: 'Warm, tearful clarity',
            },
            emotion: 'Acceptance and relief',
            sound: 'Soft piano arpeggio, distant morning birdsong.',
          },
          {
            shotId: 'S03_SH02',
            durationSeconds: 5,
            framing: 'Medium Shot (MS)',
            cameraMovement: 'Pull-Back',
            characters: ['Maya', 'The Living Shadow'],
            location: "Maya's Attic Bedroom",
            whatWeSee:
              'Maya switches off the harsh desk lamp, letting soft dawn fill the room. As she steps toward the window, the shadow glides smoothly in sync with her stride.',
            dialogue: {
              speaker: 'Maya',
              line: "Come on. Let's go ask her together.",
              delivery: 'Calm, resolute',
            },
            emotion: 'Quiet courage',
            sound: 'Warm acoustic chord resolving cleanly.',
          },
          {
            shotId: 'S03_SH03',
            durationSeconds: 4,
            framing: 'Wide Shot (WS)',
            cameraMovement: 'Static',
            characters: ['Maya', 'The Living Shadow'],
            location: "Maya's Attic Bedroom",
            whatWeSee:
              'From behind Maya at the window, morning gold bathes the rooftops outside while her shadow stretches cleanly across the floorboards like an anchor.',
            dialogue: null,
            emotion: 'Peaceful resolution',
            sound: 'Gentle morning wind fading out.',
          },
        ],
      },
    ],
  }
}
