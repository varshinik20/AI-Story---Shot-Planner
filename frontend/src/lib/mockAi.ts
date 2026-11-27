import type { ChatMessage, Conversation, InterviewStep, UploadedAttachment } from '@/types/chat'
import type { Shot, ShotPlanner } from '@/types/planner'
import type { StoryDraftState, StoryImprovementSuggestion } from '@/types/story'
import { BOY_WHO_CRIED_WOLF_PLANNER } from '@/data/boyWhoCriedWolf'
import { SHADOW_SUGGESTIONS, generateCustomShotPlanner } from '@/data/sampleStory'
import { generateId } from './utils'

export interface SimulatedReplyResult {
  assistantMessage: ChatMessage
  nextStep: InterviewStep
  updatedDraft: Partial<StoryDraftState>
  generatedPlanner?: ShotPlanner
  suggestedTitle?: string
}

function deriveTitleFromPrompt(prompt: string): string {
  const cleaned = prompt
    .replace(/^(transform|develop|write|create|build|help me explore).*?:/i, '')
    .trim()
  if (/boy who cried wolf/i.test(cleaned)) return 'The Boy Who Cried Wolf'
  if (/shadow/i.test(cleaned)) return 'The Shadow Within'
  if (/lighthouse/i.test(cleaned)) return 'The Lighthouse Bottle'
  if (/greenhouse|orbital/i.test(cleaned)) return 'Orbital Greenhouse'
  const words = cleaned.split(/\s+/).slice(0, 5).join(' ')
  return words.length > 36 ? `${words.slice(0, 36)}...` : words || 'Untitled Story'
}

export function buildSimulatedAiReply(
  conversation: Conversation,
  userText: string,
  attachment?: UploadedAttachment
): SimulatedReplyResult {
  const lower = userText.toLowerCase()
  const step = conversation.interviewStep

  // If user uploaded a document or explicitly asks to transform a full story into a shot plan immediately
  if (
    attachment ||
    (/boy who cried wolf/i.test(lower) && step === 'idle') ||
    (/transform.*shot plan|generate.*shot plan|create.*shot planner|make.*shot list/i.test(lower) &&
      userText.length > 90)
  ) {
    if (/boy who cried wolf/i.test(lower)) {
      const clonedPlanner: ShotPlanner = JSON.parse(JSON.stringify(BOY_WHO_CRIED_WOLF_PLANNER))
      clonedPlanner.id = generateId('planner')
      return {
        suggestedTitle: 'The Boy Who Cried Wolf',
        nextStep: 'planned',
        updatedDraft: {
          title: 'The Boy Who Cried Wolf',
          premise: clonedPlanner.overview.logline,
        },
        generatedPlanner: clonedPlanner,
        assistantMessage: {
          id: generateId('msg'),
          role: 'assistant',
          createdAt: Date.now(),
          content:
            "I've mapped **The Boy Who Cried Wolf** into a complete **3-scene, 17-shot production plan** (**73 seconds**, **13 dialogue lines**).\n\nExplore the overview, characters, locations, and expandable scene shots below—you can edit any shot individually or export the full breakdown as a PDF.",
          plannerId: clonedPlanner.id,
          isApprovalCard: true,
        },
      }
    }

    const title = attachment
      ? attachment.name.replace(/\.(pdf|txt|docx)$/i, '')
      : deriveTitleFromPrompt(userText)

    const draft: StoryDraftState = {
      ...conversation.storyDraft,
      title,
      premise: attachment
        ? `Story adapted from uploaded ${attachment.type.toUpperCase()} script "${attachment.name}".`
        : userText,
      segments: [userText || `Imported narrative from ${attachment?.name}`],
    }

    const planner = generateCustomShotPlanner(draft)
    const suggestions: StoryImprovementSuggestion[] = [
      {
        id: generateId('sug'),
        sectionTitle: 'Opening Visual Anchor',
        originalSegment:
          attachment?.previewText ||
          userText.slice(0, 140) ||
          'The protagonist enters the scene quietly.',
        suggestedImprovement:
          'Open on a tactile close-up of the central object before pulling wide to reveal the protagonist alone against the shifting weather.',
        explanation:
          'Starting with an intimate visual motif anchors audience curiosity before establishing the broader environment.',
        status: 'pending',
      },
    ]

    return {
      suggestedTitle: title,
      nextStep: 'planned',
      updatedDraft: draft,
      generatedPlanner: planner,
      assistantMessage: {
        id: generateId('msg'),
        role: 'assistant',
        createdAt: Date.now(),
        content: attachment
          ? `I've reviewed **${attachment.name}** (${attachment.type.toUpperCase()}) and drafted an optional story polish suggestion alongside your **scene-wise and shot-wise production plan** below.`
          : `I've transformed your story into an initial **production shot plan** below, plus one optional narrative polish suggestion you can accept or reject independently.`,
        suggestions,
        plannerId: planner.id,
        isApprovalCard: true,
      },
    }
  }

  // Step 0 (idle): User just entered a one-line story idea or prompt
  if (step === 'idle') {
    const title = deriveTitleFromPrompt(userText)
    const isShadowPrompt = /shadow/i.test(lower)

    return {
      suggestedTitle: title,
      nextStep: 'relationship',
      updatedDraft: {
        title,
        premise: userText,
        segments: [userText],
      },
      assistantMessage: {
        id: generateId('msg'),
        role: 'assistant',
        createdAt: Date.now(),
        content: isShadowPrompt
          ? "That's an intriguing concept! It could become a psychological fantasy or supernatural mystery.\n\nBefore developing the story, let's establish the central relationship.\n\n**What does the shadow want?**"
          : `That's a vivid premise for **${title}**! Before we shape the scenes and camera work, let's lock the core dramatic tension.\n\n**What drives the protagonist's central conflict?**`,
        options: isShadowPrompt
          ? [
              { id: generateId('opt'), label: 'Protect the girl.', action: 'send' },
              { id: generateId('opt'), label: 'Replace the girl.', action: 'send' },
              { id: generateId('opt'), label: 'Reveal a hidden truth.', action: 'send' },
              {
                id: generateId('opt'),
                label: 'Let me explain in my own words.',
                action: 'focus_input',
              },
            ]
          : [
              { id: generateId('opt'), label: 'Protect someone they love.', action: 'send' },
              { id: generateId('opt'), label: 'Uncover a buried truth.', action: 'send' },
              { id: generateId('opt'), label: 'Escape an impossible choice.', action: 'send' },
              {
                id: generateId('opt'),
                label: 'Let me explain in my own words.',
                action: 'focus_input',
              },
            ],
      },
    }
  }

  // Step 1 (relationship) -> provide inline Story Improvement Suggestions + Visual Style interview question
  if (step === 'relationship') {
    const suggestions: StoryImprovementSuggestion[] = SHADOW_SUGGESTIONS.map((s) => ({
      ...s,
      id: generateId('sug'),
      status: 'pending',
    }))

    return {
      nextStep: 'visual_style',
      updatedDraft: {
        shadowMotive: userText,
        segments: [
          ...conversation.storyDraft.segments,
          `Core motivation: ${userText}`,
        ],
      },
      assistantMessage: {
        id: generateId('msg'),
        role: 'assistant',
        createdAt: Date.now(),
        content: `Strong choice—anchoring the story around **"${userText.replace(/\.$/, '')}"** gives every scene clear emotional momentum.\n\nBefore we move to shot planning, here are two optional **story improvement suggestions**. Accept or reject each independently—your draft only updates when you approve.\n\nAlso, **what visual direction do you imagine for this story?**`,
        suggestions,
        options: [
          { id: generateId('opt'), label: 'Cinematic realism.', action: 'send' },
          { id: generateId('opt'), label: 'Hand-painted animation.', action: 'send' },
          { id: generateId('opt'), label: 'Anime.', action: 'send' },
          { id: generateId('opt'), label: 'Dark fantasy.', action: 'send' },
          { id: generateId('opt'), label: 'Documentary style.', action: 'send' },
          { id: generateId('opt'), label: 'Custom direction.', action: 'focus_input' },
        ],
      },
    }
  }

  // Step 2 (visual_style) -> Mood & Character Emotions interview
  if (step === 'visual_style') {
    return {
      nextStep: 'mood_emotion',
      updatedDraft: {
        visualStyle: userText,
      },
      assistantMessage: {
        id: generateId('msg'),
        role: 'assistant',
        createdAt: Date.now(),
        content: `**${userText.replace(/\.$/, '')}** will give the lighting, color contrast, and framing a strong signature.\n\nNext, let's define the **overall mood and emotional arc** for the audience:`,
        options: [
          {
            id: generateId('opt'),
            label: 'Suspenseful and intimate, shifting toward quiet relief.',
            action: 'send',
          },
          {
            id: generateId('opt'),
            label: 'Melancholic and atmospheric from start to finish.',
            action: 'send',
          },
          {
            id: generateId('opt'),
            label: 'Tense thriller energy with sharp emotional turns.',
            action: 'send',
          },
          { id: generateId('opt'), label: 'Describe mood in my own words.', action: 'focus_input' },
        ],
      },
    }
  }

  // Step 3 (mood_emotion) -> Camera Preferences & Ending Intention
  if (step === 'mood_emotion') {
    return {
      nextStep: 'camera_ending',
      updatedDraft: {
        mood: userText,
      },
      assistantMessage: {
        id: generateId('msg'),
        role: 'assistant',
        createdAt: Date.now(),
        content: `Got it—we'll pace the scenes around that emotional arc.\n\nLast creative intent question before I build the shot breakdown: **what camera style and ending intention fit best?**`,
        options: [
          {
            id: generateId('opt'),
            label: 'Slow push-ins and wide stillness, ending on a hopeful revelation.',
            action: 'send',
          },
          {
            id: generateId('opt'),
            label: 'Intimate handheld tracking with an ambiguous, haunting final frame.',
            action: 'send',
          },
          {
            id: generateId('opt'),
            label: 'Generate the complete shot plan now.',
            action: 'send',
          },
        ],
      },
    }
  }

  // Step 4 (camera_ending or ready_for_plan) -> Generate full Shot Planner inside conversation
  if (step === 'camera_ending' || step === 'ready_for_plan') {
    const mergedDraft: StoryDraftState = {
      ...conversation.storyDraft,
      cameraPreference: userText,
      endingIntention: userText,
    }
    const planner = generateCustomShotPlanner(mergedDraft)
    return {
      nextStep: 'planned',
      updatedDraft: mergedDraft,
      generatedPlanner: planner,
      assistantMessage: {
        id: generateId('msg'),
        role: 'assistant',
        createdAt: Date.now(),
        content: `Here is your complete **StoryForge Production Shot Plan** for **${planner.overview.filmTitle}**, incorporating your visual direction and creative intent.\n\nExpand any scene or shot below to review all 10 production fields, make shot-level edits, or export the production PDF.`,
        plannerId: planner.id,
        isApprovalCard: true,
      },
    }
  }

  // Step 5 (planned): Follow-up conversational guidance / notes
  return {
    nextStep: 'planned',
    updatedDraft: {},
    assistantMessage: {
      id: generateId('msg'),
      role: 'assistant',
      createdAt: Date.now(),
      content: `Noted! You can apply that adjustment directly to any individual shot using the **Edit** or **Regenerate Shot** control inside the scenes above—without overwriting the rest of your shot plan.\n\nIf you'd like, click **Approve Shot Planner** at the bottom of the breakdown once you're ready to export your production PDF.`,
    },
  }
}

export function simulateShotRegeneration(shot: Shot, feedback: string): Shot {
  const lower = feedback.toLowerCase()
  let nextCamera = shot.cameraMovement
  let nextFraming = shot.framing
  let nextDuration = shot.durationSeconds

  if (/push|tight|closer|zoom/i.test(lower)) {
    nextCamera = 'Slow Push-In'
    nextFraming = 'Close-Up (CU)'
  } else if (/wide|establish|pull/i.test(lower)) {
    nextCamera = 'Pull-Back'
    nextFraming = 'Wide Shot (WS)'
  } else if (/handheld|urgent|chaotic|shake/i.test(lower)) {
    nextCamera = 'Handheld Follow'
  } else if (/pan/i.test(lower)) {
    nextCamera = 'Slow Pan Right'
  }

  if (/faster|shorter|quick/i.test(lower)) {
    nextDuration = Math.max(2, shot.durationSeconds - 1)
  } else if (/longer|slower|hold|linger/i.test(lower)) {
    nextDuration = shot.durationSeconds + 2
  }

  return {
    ...shot,
    cameraMovement: nextCamera,
    framing: nextFraming,
    durationSeconds: nextDuration,
    whatWeSee: `${shot.whatWeSee} [Refined: ${feedback.trim()}]`,
    emotion: /tense|tension|dark|fear|dramatic/i.test(lower)
      ? `${shot.emotion} (heightened tension)`
      : shot.emotion,
    regeneratedNote: `Regenerated from note: "${feedback.trim()}"`,
  }
}
