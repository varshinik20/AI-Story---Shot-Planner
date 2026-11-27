import type { Conversation, StoryProject } from '@/types/chat'
import { BOY_WHO_CRIED_WOLF_PLANNER } from './boyWhoCriedWolf'
import { SHADOW_SUGGESTIONS } from './sampleStory'

export const MOCK_PROJECTS: StoryProject[] = [
  {
    id: 'proj_my_stories',
    name: 'My Story Projects',
    description: 'Active narrative drafts, interviews, and production shot plans',
  },
]

const now = Date.now()

export const INITIAL_CONVERSATIONS: Conversation[] = [
  {
    id: 'conv_boy_who_cried_wolf',
    title: 'The Boy Who Cried Wolf',
    projectId: 'proj_my_stories',
    createdAt: now - 1000 * 60 * 35,
    updatedAt: now - 1000 * 60 * 5,
    plannerId: BOY_WHO_CRIED_WOLF_PLANNER.id,
    interviewStep: 'planned',
    storyDraft: {
      title: 'The Boy Who Cried Wolf',
      premise:
        'Bored on a quiet hillside, a young shepherd stages a wolf attack for thrills—only to face silent village disbelief when a real predator emerges from the dusk.',
      segments: [
        'Leo watches the sheep in late afternoon boredom and stages a wolf panic to stir up the village.',
        'The villagers rush up the hill, discover the prank, and warn him that lies erode trust.',
        'At twilight, a real wolf stalks the flock, but the villagers dismiss Leo’s desperate cries.',
      ],
      visualStyle: 'Cinematic realism',
      mood: 'Grounded fable shifting from golden warmth to cold dread',
      cameraPreference: 'Wide landscapes contrasted with tight emotional close-ups',
      endingIntention: 'Somber moral warning',
    },
    messages: [
      {
        id: 'msg_bwcw_1',
        role: 'user',
        content:
          'Transform "The Boy Who Cried Wolf" into a complete, production-ready scene-wise and shot-wise plan with 3 scenes, 17 shots, and detailed dialogue delivery.',
        createdAt: now - 1000 * 60 * 35,
      },
      {
        id: 'msg_bwcw_2',
        role: 'assistant',
        content:
          "I've structured **The Boy Who Cried Wolf** into a complete 3-scene, 17-shot production plan (**73 seconds** total runtime, **13 dialogue lines**).\n\nBelow you'll find the **Project Overview**, **4 Character Profiles**, **3 Location Descriptions**, and the interactive **Scene-by-Scene Shot Breakdown**. Click any scene or shot to inspect all 10 production fields, edit individual shots, or regenerate a single shot with notes.",
        createdAt: now - 1000 * 60 * 34,
        plannerId: BOY_WHO_CRIED_WOLF_PLANNER.id,
        isApprovalCard: true,
      },
    ],
  },
  {
    id: 'conv_shadow_within',
    title: 'The Shadow Within',
    projectId: 'proj_my_stories',
    createdAt: now - 1000 * 60 * 120,
    updatedAt: now - 1000 * 60 * 90,
    interviewStep: 'visual_style',
    storyDraft: {
      title: 'The Shadow Within',
      premise: 'A girl discovers that her shadow has a life of its own.',
      shadowMotive: 'Reveal a hidden truth.',
      segments: [
        'Maya walked home from school and noticed her shadow did not match her steps on the sidewalk.',
        'She tried to run away from the shadow inside her bedroom, feeling very scared.',
      ],
    },
    messages: [
      {
        id: 'msg_sw_1',
        role: 'user',
        content: 'A girl discovers that her shadow has a life of its own.',
        createdAt: now - 1000 * 60 * 120,
      },
      {
        id: 'msg_sw_2',
        role: 'assistant',
        content:
          "That's an intriguing concept! It could become a psychological fantasy or supernatural mystery.\n\nBefore developing the story, let's establish the central relationship.\n\n**What does the shadow want?**",
        createdAt: now - 1000 * 60 * 119,
        selectedOptionId: 'opt_reveal',
        options: [
          { id: 'opt_protect', label: 'Protect the girl.', action: 'send' },
          { id: 'opt_replace', label: 'Replace the girl.', action: 'send' },
          { id: 'opt_reveal', label: 'Reveal a hidden truth.', action: 'send' },
          { id: 'opt_custom', label: 'Let me explain in my own words.', action: 'focus_input' },
        ],
      },
      {
        id: 'msg_sw_3',
        role: 'user',
        content: 'Reveal a hidden truth.',
        createdAt: now - 1000 * 60 * 110,
      },
      {
        id: 'msg_sw_4',
        role: 'assistant',
        content:
          "Great direction—making the shadow a messenger of a buried family secret turns fear into discovery.\n\nI've drafted two **story improvement suggestions** to sharpen the visual imagery before we lock the shot style. Review each suggestion below—nothing changes in your draft unless you accept it.",
        createdAt: now - 1000 * 60 * 109,
        suggestions: SHADOW_SUGGESTIONS.map((s) => ({ ...s })),
      },
      {
        id: 'msg_sw_5',
        role: 'assistant',
        content:
          "Next, let's align on creative direction so the shots match your vision.\n\n**What visual direction do you imagine for this story?**",
        createdAt: now - 1000 * 60 * 108,
        options: [
          { id: 'vis_realism', label: 'Cinematic realism.', action: 'send' },
          { id: 'vis_painted', label: 'Hand-painted animation.', action: 'send' },
          { id: 'vis_anime', label: 'Anime.', action: 'send' },
          { id: 'vis_dark', label: 'Dark fantasy.', action: 'send' },
          { id: 'vis_doc', label: 'Documentary style.', action: 'send' },
          { id: 'vis_custom', label: 'Custom direction.', action: 'focus_input' },
        ],
      },
    ],
  },
  {
    id: 'conv_lost_kingdom',
    title: 'The Lost Kingdom',
    projectId: 'proj_my_stories',
    createdAt: now - 1000 * 60 * 60 * 24,
    updatedAt: now - 1000 * 60 * 60 * 22,
    interviewStep: 'mood_emotion',
    storyDraft: {
      title: 'The Lost Kingdom',
      premise:
        'An archivist discovers a sunken brass astrolabe that projects star maps of a vanished coastal empire.',
      visualStyle: 'Hand-painted animation',
      segments: [
        'Elena dusts off a sea-corroded astrolabe in the harbor archive as tidewaters rise against the seawall.',
      ],
    },
    messages: [
      {
        id: 'msg_lk_1',
        role: 'user',
        content:
          'An archivist discovers a sunken brass astrolabe that projects star maps of a vanished coastal empire.',
        createdAt: now - 1000 * 60 * 60 * 24,
      },
      {
        id: 'msg_lk_2',
        role: 'assistant',
        content:
          "A coastal mystery steeped in lost history! **Hand-painted animation** will give the brass reflections and sea mist a tactile storybook warmth.\n\nLet's shape the emotional core before breaking it into scenes: **what should the audience feel most strongly in the opening minute?**",
        createdAt: now - 1000 * 60 * 60 * 23,
        options: [
          { id: 'lk_wonder', label: 'Quiet wonder and nostalgia.', action: 'send' },
          { id: 'lk_urgency', label: 'Mounting urgency against the rising tide.', action: 'send' },
          { id: 'lk_melancholy', label: 'Melancholy for what was forgotten.', action: 'send' },
        ],
      },
    ],
  },
  {
    id: 'conv_journey_home',
    title: 'A Journey Home',
    projectId: 'proj_my_stories',
    createdAt: now - 1000 * 60 * 60 * 48,
    updatedAt: now - 1000 * 60 * 60 * 46,
    interviewStep: 'camera_ending',
    storyDraft: {
      title: 'A Journey Home',
      premise:
        'After ten years abroad, a violinist rides an overnight sleeper train back to a quiet mountain town with an unplayed score in her case.',
      visualStyle: 'Cinematic realism',
      mood: 'Tender and contemplative',
      segments: [
        'Clara watches rain streak across the sleeper car window while rehearsing the opening bars silently on her wrist.',
      ],
    },
    messages: [
      {
        id: 'msg_jh_1',
        role: 'user',
        content:
          'After ten years abroad, a violinist rides an overnight sleeper train back to a quiet mountain town with an unplayed score in her case.',
        createdAt: now - 1000 * 60 * 60 * 48,
      },
      {
        id: 'msg_jh_2',
        role: 'assistant',
        content:
          "Beautifully grounded premise. With **Cinematic realism** and a **tender, contemplative** tone, natural window reflections and rhythmic train audio will carry half the storytelling.\n\nBefore I generate your full shot plan, **how should the camera move and how do you want the ending to land?**",
        createdAt: now - 1000 * 60 * 60 * 47,
        options: [
          {
            id: 'jh_opt_1',
            label: 'Gentle dolly push-ins with a hopeful reunion ending.',
            action: 'send',
          },
          {
            id: 'jh_opt_2',
            label: 'Intimate handheld framing with an open-ended final note.',
            action: 'send',
          },
          {
            id: 'jh_opt_3',
            label: 'Static, composed wide frames with a bittersweet parting.',
            action: 'send',
          },
        ],
      },
    ],
  },
]
