import type {
  IntakeFieldKey,
  QuestionSelectionResult,
  StoryIntakeState,
} from '../types/storyIntake.types'

const FIELD_PRIORITY: IntakeFieldKey[] = ['story_title', 'visual_style', 'story_context']

export function getMissingIntakeFields(state: StoryIntakeState): IntakeFieldKey[] {
  const missing: IntakeFieldKey[] = []
  if (!state.storyTitle.provided || !state.storyTitle.value) missing.push('story_title')
  if (!state.visualStyle.provided || !state.visualStyle.value) missing.push('visual_style')
  if (!state.storyContext.provided || !state.storyContext.value) missing.push('story_context')
  return missing
}

export function buildTitleSuggestions(state: StoryIntakeState): string[] {
  const ctx = (state.storyContext.value || '').toLowerCase()
  const style = (state.visualStyle.value || '').toLowerCase()

  if (/\bshadow\b/.test(ctx)) {
    return ['The Shadow Within', 'Whispers Behind the Glass', 'Echoes in the Dark']
  }
  if (/\bsun\b|\bdark\b/.test(ctx) || /\bdark fantasy\b/.test(style)) {
    return ['The Last Light', 'Before the Dawn Fades', 'Ashes of the Sun']
  }
  if (/\bmemory|memories\b/.test(ctx)) {
    return ['Fragments of Yesterday', 'The Memory Weaver', 'Echoes She Kept']
  }
  if (/\bbrother|sister|missing\b/.test(ctx)) {
    return ['Steps in the Fog', 'The Road Back to You', 'Where the River Turns']
  }
  if (/\banime\b/.test(style)) {
    return ['Paper Lanterns at Dusk', 'The Glass Horizon', 'Echoes Across the Sky']
  }
  return ['The Last Light', 'The Shadow Within', 'Beyond the Horizon']
}

function formatPremiseFragment(premise: string): string {
  const trimmed = premise.trim().replace(/[.]+$/, '')
  if (!trimmed) return 'an unfolding mystery'
  const lowerStart = trimmed.charAt(0).toLowerCase() + trimmed.slice(1)
  return lowerStart
}

export function selectNextQuestion(
  state: StoryIntakeState,
  acknowledgementPrefix?: string
): QuestionSelectionResult {
  const missing = getMissingIntakeFields(state)
  const nextField = FIELD_PRIORITY.find((field) => missing.includes(field)) ?? null

  if (!nextField) {
    return {
      nextField: null,
      questionText: buildConfirmationSummaryText(state),
      includeStyleSuggestions: false,
    }
  }

  const title = state.storyTitle.value
  const style = state.visualStyle.value
  const context = state.storyContext.value
  const hasTitle = state.storyTitle.provided && Boolean(title)
  const hasStyle = state.visualStyle.provided && Boolean(style)
  const hasContext = state.storyContext.provided && Boolean(context)

  let question = ''
  if (nextField === 'story_title') {
    if (!hasStyle && !hasContext) {
      question =
        "Of course! I'd love to help you create one. Let's start with a title. Do you already have a name in mind, or would you like me to suggest one?"
    } else if (hasStyle && !hasContext) {
      question = `A ${style!.toLowerCase()} story sounds great! Do you already have a title in mind for it, or would you like me to suggest a few?`
    } else if (!hasStyle && hasContext) {
      question = `That sounds like an intriguing premise. What would you like to title this story, or should I suggest a few options?`
    } else {
      question = `Love the ${style!.toLowerCase()} direction for that premise. What would you like to title the story?`
    }
  } else if (nextField === 'visual_style') {
    if (hasTitle && !hasContext) {
      question = `That's an intriguing title! What kind of visual world are you imagining for **${title}**? Something dark and mysterious, cinematic, anime-inspired, or perhaps a completely different style?`
    } else if (hasTitle && hasContext) {
      question = `I love that idea for **${title}**. How do you picture the visual world—cinematic realism, anime, hand-painted animation, dark fantasy, or another look?`
    } else {
      question =
        'What kind of visual world are you imagining for this story? Something cinematic, anime-inspired, dark fantasy, or a style of your own?'
    }
  } else if (nextField === 'story_context') {
    if (hasTitle && hasStyle) {
      question = `Love that direction! Now tell me a little about the story itself. What's happening in **${title}**? You can share just a rough idea, and we'll develop it together.`
    } else if (hasTitle) {
      question = `Now tell me a little about **${title}**. What's the story about? Even a rough idea is plenty to get started.`
    } else {
      question =
        "What's the story about? You can share just a rough idea, a character, or a turning point, and we'll build from there."
    }
  }

  const fullText = acknowledgementPrefix ? `${acknowledgementPrefix}\n\n${question}` : question

  return {
    nextField,
    questionText: fullText,
    includeStyleSuggestions: nextField === 'visual_style',
  }
}

export function buildConfirmationSummaryText(state: StoryIntakeState): string {
  const title = state.storyTitle.value ?? 'Untitled'
  const styleDetails = state.visualStyle.details
  const styleText = state.visualStyle.value ?? 'your chosen style'
  const stylePhrase =
    styleDetails?.lighting && !styleText.toLowerCase().includes(styleDetails.lighting.toLowerCase())
      ? `${styleText.toLowerCase()} with ${styleDetails.lighting.toLowerCase()} lighting`
      : styleText.toLowerCase()
  const contextFragment = state.storyContext.value
    ? formatPremiseFragment(state.storyContext.value)
    : 'your story premise'

  const toneNote = /dark|shadow|mystery|mysterious/i.test(
    `${styleText} ${state.storyContext.value ?? ''}`
  )
    ? "I'd love to develop this into something atmospheric and suspenseful."
    : "I'd love to develop this into a vivid, cohesive story."

  return [
    `That's a fascinating premise! So we're creating **${title}**, with a ${stylePhrase} visual style, about ${contextFragment}.`,
    '',
    `${toneNote} Shall we start building the story?`,
  ].join('\n')
}
