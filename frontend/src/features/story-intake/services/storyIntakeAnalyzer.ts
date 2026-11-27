import type {
  AnalyzeIntakeInput,
  ExtractedContextValue,
  ExtractedFieldValue,
  IntakeAnalysisResult,
  IntakeFieldKey,
  IntakeIntent,
  StoryIntakeAnalyzer,
  VisualDetails,
} from '../types/storyIntake.types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

const KNOWN_VISUAL_STYLES: Array<{ pattern: RegExp; label: string; medium?: string }> = [
  { pattern: /\bcinematic realism\b/i, label: 'Cinematic realism', medium: 'Live-action realism' },
  { pattern: /\bhand[- ]painted animation\b/i, label: 'Hand-painted animation', medium: 'Animation' },
  { pattern: /\b3d animation\b|\bpixar\b|\bcgi\b/i, label: '3D animation', medium: '3D animation' },
  { pattern: /\bwatercolor illustration\b|\bwatercolor\b/i, label: 'Watercolor illustration', medium: 'Illustration' },
  { pattern: /\bscience[- ]fiction cinematic\b|\bsci[- ]fi cinematic\b/i, label: 'Science-fiction cinematic', medium: 'Live-action sci-fi' },
  { pattern: /\bdocumentary style\b|\bdocumentary\b/i, label: 'Documentary style', medium: 'Documentary' },
  { pattern: /\bdark fantasy\b/i, label: 'Dark fantasy', medium: 'Dark fantasy' },
  { pattern: /\banime\b/i, label: 'Anime', medium: 'Anime' },
]

function computeMissingFields(
  titleProvided: boolean,
  styleProvided: boolean,
  contextProvided: boolean
): IntakeFieldKey[] {
  const missing: IntakeFieldKey[] = []
  if (!titleProvided) missing.push('story_title')
  if (!styleProvided) missing.push('visual_style')
  if (!contextProvided) missing.push('story_context')
  return missing
}

function cleanPhrase(raw: string): string {
  return raw.trim().replace(/^["'“”‘’]+|["'“”‘’.,!?;:]+$/g, '').trim()
}

function extractVisualStyleFromText(
  text: string,
  pendingField: IntakeFieldKey | null
): ExtractedFieldValue<VisualDetails> {
  const trimmed = text.trim()

  // Explicit modification phrase: "change the style to ..." / "make it look like ..."
  const explicitChange = trimmed.match(
    /(?:change|switch|update|set)\s+(?:the\s+)?(?:visual\s+)?style\s+to\s+([^.!\n]+)/i
  )
  if (explicitChange?.[1]) {
    const candidate = cleanPhrase(explicitChange[1])
    const matched = KNOWN_VISUAL_STYLES.find((s) => s.pattern.test(candidate))
    return {
      value: matched ? matched.label : capitalizeFirst(candidate),
      provided: true,
      confidence: 0.96,
      details: matched?.medium ? { medium: matched.medium } : undefined,
    }
  }

  // Natural-language descriptive visual cues (e.g. "looks like a dark, mysterious animated film with deep blue lighting")
  const lookLikeMatch = trimmed.match(
    /(?:looks?\s+like|visual\s+style\s*(?:is|should\s+be|:)|in\s+(?:a|an)\s+)([^.\n]+?(?:film|animation|animated|style|illustration|lighting|aesthetic|look|realism|fantasy|anime)[^.\n]*)/i
  )

  const hasLighting = /\b([a-z]+(?:\s+[a-z]+)?)\s+lighting\b/i.exec(trimmed)
  const hasAnimated = /\banimated(?:\s+film)?\b|\banimation\b/i.test(trimmed)
  const hasMoodWords = trimmed.match(/\b(dark|mysterious|warm|bleak|dreamy|noir|gritty|ethereal|whimsical|moody|neon|atmospheric)\b/gi)

  // Check exact/known style labels first unless rich custom lighting/mood phrasing accompanies it
  for (const style of KNOWN_VISUAL_STYLES) {
    if (style.pattern.test(trimmed)) {
      const details: VisualDetails = {}
      if (style.medium) details.medium = style.medium
      if (hasLighting?.[1]) details.lighting = capitalizeFirst(hasLighting[1])
      if (hasMoodWords && hasMoodWords.length > 0) {
        details.mood = Array.from(new Set(hasMoodWords.map((w) => capitalizeFirst(w)))).join(', ')
      }

      // If user described "dark fantasy animation with atmospheric lighting", preserve richer description when > 1 detail
      if (hasAnimated && style.label === 'Dark fantasy') {
        return {
          value: 'Dark fantasy animation',
          provided: true,
          confidence: 0.96,
          details: { ...details, medium: 'Animation' },
        }
      }

      return {
        value: style.label,
        provided: true,
        confidence: 0.97,
        details: Object.keys(details).length > 0 ? details : undefined,
      }
    }
  }

  if (lookLikeMatch || (hasAnimated && (hasMoodWords || hasLighting)) || hasLighting) {
    const details: VisualDetails = {}
    if (hasAnimated) details.medium = 'Animation'
    if (hasLighting?.[1]) details.lighting = capitalizeFirst(hasLighting[1])
    if (hasMoodWords && hasMoodWords.length > 0) {
      details.mood = Array.from(new Set(hasMoodWords.map((w) => capitalizeFirst(w)))).join(', ')
    }

    const descriptiveSource = lookLikeMatch?.[1] ? cleanPhrase(lookLikeMatch[1]) : cleanPhrase(trimmed)
    const compactLabel =
      hasAnimated && hasMoodWords && hasMoodWords.length > 0
        ? `${Array.from(new Set(hasMoodWords.map((w) => w.toLowerCase()))).slice(0, 2).map(capitalizeFirst).join(' ')} animation`
        : descriptiveSource.length <= 72
        ? capitalizeFirst(descriptiveSource)
        : `${capitalizeFirst(descriptiveSource.slice(0, 69))}...`

    return {
      value: compactLabel,
      provided: true,
      confidence: 0.9,
      details,
    }
  }

  // Direct answer when the pending question specifically asked for visual_style
  if (
    pendingField === 'visual_style' &&
    trimmed.length >= 3 &&
    !/^(idk|not sure|anything|whatever|no idea|suggest|help)\b/i.test(trimmed) &&
    !/\?$/.test(trimmed)
  ) {
    return {
      value: capitalizeFirst(cleanPhrase(trimmed)),
      provided: true,
      confidence: 0.88,
    }
  }

  return { value: null, provided: false, confidence: 0 }
}

function extractTitleFromText(
  text: string,
  pendingField: IntakeFieldKey | null
): ExtractedFieldValue {
  const trimmed = text.trim()

  // Explicit title change: "Change the title to The Forgotten Light"
  const changeTitleMatch = trimmed.match(
    /(?:change|rename|update|set)\s+(?:the\s+)?title\s+to\s+["'“]?([^"'\n”.,!?]+)["'”]?/i
  )
  if (changeTitleMatch?.[1]) {
    return {
      value: cleanPhrase(changeTitleMatch[1]),
      provided: true,
      confidence: 0.98,
    }
  }

  // "called X" / "titled X" / "named X"
  const calledMatch = trimmed.match(
    /\b(?:called|titled|named|title\s+is|title\s*:)\s+["'“]?([^"'”\n,.;!?]+)["'”]?/i
  )
  if (calledMatch?.[1]) {
    const titleCandidate = cleanPhrase(calledMatch[1])
    if (titleCandidate.length >= 2) {
      return {
        value: titleCandidate,
        provided: true,
        confidence: 0.97,
      }
    }
  }

  // Quoted title anywhere: e.g. Create "The Last Light"
  const quotedMatch = trimmed.match(/["“]([^"”]{2,60})["”]/)
  if (quotedMatch?.[1]) {
    return {
      value: cleanPhrase(quotedMatch[1]),
      provided: true,
      confidence: 0.94,
    }
  }

  // Pattern 1: "Create <Title> in <style> style" / "Create <Title>, a <style> story..." / "Create <Title> an anime story"
  const createWithQualifier = trimmed.match(
    /^(?:create|make|develop|write|start|plan)\s+(?:the\s+story\s+)?([A-Z][A-Za-z0-9'’-]*(?:\s+[A-Z0-9][A-Za-z0-9'’-]*){0,6})(?=\s*(?:,|in\s+[a-z\s]+\s+style|\babout\b|\b(?:a|an)\s+(?:anime|dark\s+fantasy|cinematic|hand[- ]painted|3d|watercolor|documentary|sci[- ]fi)))/i
  )
  if (createWithQualifier?.[1]) {
    const candidate = cleanPhrase(createWithQualifier[1])
    const lower = candidate.toLowerCase()
    const isGenericPhrase =
      /^(a|an|the)\s+(story|film|movie|anime|dark fantasy|sci-fi|cinematic)/i.test(lower) ||
      /\b(story|film|tale)\b/i.test(lower) ||
      KNOWN_VISUAL_STYLES.some((s) => s.pattern.test(lower))

    if (!isGenericPhrase && candidate.split(/\s+/).length <= 7) {
      return {
        value: candidate,
        provided: true,
        confidence: 0.93,
      }
    }
  }

  // Pattern 2: Standalone "Create <Title>." (e.g. "Create The Shadow Within.")
  const standaloneCreate = trimmed.match(
    /^(?:[Cc]reate|[Mm]ake|[Dd]evelop|[Ww]rite|[Ss]tart|[Pp]lan)\s+(?:a\s+story\s+called\s+|the\s+story\s+)?([A-Z][A-Za-z0-9'’-]*(?:\s+[A-Za-z0-9'’-]+){0,6})[.!?]*$/
  )
  if (standaloneCreate?.[1]) {
    const candidate = cleanPhrase(standaloneCreate[1])
    const lower = candidate.toLowerCase()
    const isGenericPhrase =
      /^(a|an|the)\b/i.test(lower) && /\b(story|film|movie|tale)\b/i.test(lower)
    const isStyleOnly = KNOWN_VISUAL_STYLES.some((s) => s.pattern.test(lower))
    if (!isGenericPhrase && !isStyleOnly && !/\b(story|film|tale)\b/i.test(lower)) {
      return {
        value: candidate,
        provided: true,
        confidence: 0.92,
      }
    }
  }

  // Direct answer when pending question is story_title
  if (
    pendingField === 'story_title' &&
    trimmed.length >= 2 &&
    trimmed.length <= 80 &&
    !/\b(suggest|idea|recommend|help|don't know|dont know|not sure|no idea)\b/i.test(trimmed) &&
    !/\?$/.test(trimmed)
  ) {
    // Avoid mistaking a full "about ..." premise or style reply for a title
    const looksLikeStyle = KNOWN_VISUAL_STYLES.some((s) => s.pattern.test(trimmed))
    const looksLikeContext = /^(?:it'?s\s+about|a\s+story\s+about|about\s+)/i.test(trimmed)
    if (!looksLikeStyle && !looksLikeContext) {
      return {
        value: cleanPhrase(trimmed),
        provided: true,
        confidence: 0.9,
      }
    }
  }

  return { value: null, provided: false, confidence: 0 }
}

function extractContextMetadata(text: string): { theme: string | null; mainConflict: string | null } {
  const lower = text.toLowerCase()
  let theme: string | null = null
  let mainConflict: string | null = null

  if (/\btrust\b|\bdishonest|\blie\b|\blies\b|\bbetray/i.test(lower)) {
    theme = 'Trust'
    if (/\blie\b|\blies\b|\bdishonest/i.test(lower)) {
      mainConflict = 'Repeated dishonesty and rebuilding trust'
    }
  } else if (/\bmissing\b|\bsearch|\blost\b/i.test(lower)) {
    theme = 'Loss and devotion'
    mainConflict = 'Searching for someone missing'
  } else if (/\bshadow\b|\bsecret\b|\bhidden truth/i.test(lower)) {
    theme = 'Self-discovery and hidden truth'
  } else if (/\bsun disappears\b|\bsaving\b|\bsave\b/i.test(lower)) {
    theme = 'Courage and survival'
    mainConflict = 'Saving a community from encroaching darkness'
  } else if (/\bmemor(y|ies)\b/i.test(lower)) {
    theme = 'Memory and empathy'
  }

  return { theme, mainConflict }
}

function extractStoryContextFromText(
  text: string,
  pendingField: IntakeFieldKey | null
): ExtractedContextValue {
  const trimmed = text.trim()

  // Explicit context modification: "change/update the story context to ..."
  const explicitChange = trimmed.match(
    /(?:change|update|set)\s+(?:the\s+)?(?:story\s+)?(?:context|premise|plot|idea)\s+to\s+(.+)/i
  )
  if (explicitChange?.[1]) {
    const val = cleanPhrase(explicitChange[1])
    const meta = extractContextMetadata(val)
    return {
      value: capitalizeFirst(val),
      provided: true,
      confidence: 0.95,
      ...meta,
    }
  }

  // "about <premise>" or "behind <Title> is <premise>"
  const aboutMatch = trimmed.match(/\b(?:story\s+about|about|premise\s+is)\s+([^.\n]+(?:[.!?][^.\n]+)*)/i)
  if (aboutMatch?.[1]) {
    let premise = cleanPhrase(aboutMatch[1])
    // Strip trailing visual style clause if user wrote "about X in anime style"
    premise = premise.replace(/\s+in\s+[a-z\s-]+\s+style$/i, '').trim()
    const isVague =
      premise.split(/\s+/).length < 2 ||
      /^(something|anything|stuff|things|idk|whatever)$/i.test(premise)
    if (!isVague) {
      const meta = extractContextMetadata(premise)
      return {
        value: capitalizeFirst(premise),
        provided: true,
        confidence: 0.95,
        ...meta,
      }
    }
  }

  // Direct answer when pending question is story_context
  if (pendingField === 'story_context') {
    const cleaned = cleanPhrase(trimmed)
    const isVague =
      cleaned.split(/\s+/).length < 3 ||
      /^(idk|not sure|something cool|anything|no idea|a story|surprise me)$/i.test(cleaned)
    if (!isVague && !/\?$/.test(trimmed)) {
      const meta = extractContextMetadata(cleaned)
      return {
        value: capitalizeFirst(cleaned),
        provided: true,
        confidence: 0.92,
        ...meta,
      }
    }
  }

  // Additional context phrasing ("Also, she discovers..." / "Additionally, ...")
  const addContextMatch = trimmed.match(
    /^(?:also|plus|and\s+also|additionally)\s*,?\s+(.+)/i
  )
  if (addContextMatch?.[1] && addContextMatch[1].split(/\s+/).length >= 3) {
    const cleaned = cleanPhrase(addContextMatch[1])
    const meta = extractContextMetadata(cleaned)
    return {
      value: capitalizeFirst(cleaned),
      provided: true,
      confidence: 0.91,
      ...meta,
    }
  }

  // Standalone narrative premise even without "about" (e.g., "A girl discovers her shadow moves on its own.")
  const narrativeStart = trimmed.match(
    /^(?:a|an|the|in\s+a|after|when|two|three|she|he|they)\s+\w+.*\b(?:discovers?|finds?|searches?|fights?|tries?|escapes?|learns?|wakes?|notices?|loses?|saves?|can\s+\w+)\b.+/i
  )
  if (
    narrativeStart &&
    trimmed.split(/\s+/).length >= 5 &&
    !/^(?:i\s+want|create|make|write)\s+(?:a|an)\s+(?:story|film)\.?$/i.test(trimmed)
  ) {
    const cleaned = cleanPhrase(trimmed)
    const meta = extractContextMetadata(cleaned)
    return {
      value: capitalizeFirst(cleaned),
      provided: true,
      confidence: 0.9,
      ...meta,
    }
  }

  return { value: null, provided: false, confidence: 0 }
}

function capitalizeFirst(str: string): string {
  if (!str) return str
  return str.charAt(0).toUpperCase() + str.slice(1)
}

/**
 * Ensures no internal classification strings, third-person meta commentary,
 * or raw JSON ever reach the user-facing chat UI.
 */
export function sanitizeAssistantMessage(candidate: string | null | undefined): string | null {
  const cleaned = candidate?.trim()
  if (!cleaned) return null
  if (cleaned.startsWith('{') || cleaned.startsWith('[')) return null

  const lower = cleaned.toLowerCase()
  const forbiddenFragments = [
    'the user ',
    'user wants ',
    'user asks ',
    'user provided ',
    'missing_fields',
    'story_title',
    'visual_style',
    'story_context',
    'next_action',
    'missing field:',
    'intent:',
    'extracted_fields',
  ]
  if (forbiddenFragments.some((frag) => lower.includes(frag))) {
    return null
  }
  return cleaned
}

function detectGeneralQuestion(text: string): string | null {
  const trimmed = text.trim()
  if (!trimmed.endsWith('?') && !/^(what|how|why|can you|do you|could you)\b/i.test(trimmed)) {
    return null
  }
  // If they are asking for a title suggestion, handle via suggest_title intent instead
  if (/\btitle\b/i.test(trimmed) && /\bsuggest|idea|recommend|name\b/i.test(trimmed)) {
    return null
  }
  if (/\b(what can|how does|storyforge|cinemind|shots?|pdf|export|help)\b/i.test(trimmed)) {
    return 'StoryForge helps shape your story concept, visual style, and narrative premise first, and then builds a scene-by-scene, shot-by-shot production plan you can edit and export to PDF.'
  }
  return null
}

/**
 * Explicitly labelled local development analyzer used when the backend LLM
 * is unavailable or offline. Produces structured extraction output matching
 * the production JSON contract.
 */
export class LocalDevStoryIntakeAnalyzer implements StoryIntakeAnalyzer {
  async analyze(input: AnalyzeIntakeInput): Promise<IntakeAnalysisResult> {
    const trimmed = input.message.trim()
    const { currentState, hasAttachment, attachmentName } = input
    const pendingField = currentState.currentQuestion

    // 1. Complete story upload via attachment
    if (hasAttachment) {
      const titleFromFile = attachmentName
        ? attachmentName.replace(/\.(pdf|txt|docx)$/i, '').replace(/[_-]+/g, ' ').trim()
        : null
      const style = extractVisualStyleFromText(trimmed, pendingField)
      const context: ExtractedContextValue = trimmed.length > 20
        ? { value: trimmed, provided: true, confidence: 0.9 }
        : {
            value: `Story imported from document "${attachmentName ?? 'uploaded file'}".`,
            provided: true,
            confidence: 0.85,
          }
      const title: ExtractedFieldValue = titleFromFile
        ? { value: titleFromFile, provided: true, confidence: 0.85 }
        : { value: null, provided: false, confidence: 0 }

      const missing = computeMissingFields(
        Boolean(title.provided || currentState.storyTitle.provided),
        Boolean(style.provided || currentState.visualStyle.provided),
        Boolean(context.provided || currentState.storyContext.provided)
      )

      return {
        intent: 'story_upload',
        source: 'local_dev_analyzer',
        storyTitle: title,
        visualStyle: style,
        storyContext: context,
        missingFields: missing,
        readyForGeneration: missing.length === 0,
      }
    }

    // 2. Title suggestion request (e.g. "I don't have a title. Suggest some.")
    if (
      /\bsuggest\b.*\btitle\b|\btitle\b.*\bsuggest|\bneed\s+(?:a\s+)?title|\bhelp\s+(?:me\s+)?name|\b(?:don'?t|do not)\s+have\s+(?:a\s+)?title\b|\bno\s+title\b/i.test(
        trimmed
      )
    ) {
      return {
        intent: 'suggest_title',
        source: 'local_dev_analyzer',
        storyTitle: { value: null, provided: false, confidence: 0 },
        visualStyle: { value: null, provided: false, confidence: 0 },
        storyContext: { value: null, provided: false, confidence: 0 },
        missingFields: currentState.missingFields,
        readyForGeneration: false,
      }
    }

    // 2b. User prefers to explain the story context before picking title/style
    if (
      /\b(?:explain|tell|share|describe)\s+(?:the\s+)?(?:story|idea|plot|context)\s+first\b|\bstart\s+with\s+(?:the\s+)?(?:story|plot|idea)\b/i.test(
        trimmed
      )
    ) {
      return {
        intent: 'explain_story_first',
        source: 'local_dev_analyzer',
        storyTitle: { value: null, provided: false, confidence: 0 },
        visualStyle: { value: null, provided: false, confidence: 0 },
        storyContext: { value: null, provided: false, confidence: 0 },
        missingFields: currentState.missingFields,
        readyForGeneration: false,
      }
    }

    // 3. Explicit confirmation / edit requests when awaiting confirmation
    if (currentState.status === 'awaiting_confirmation') {
      if (
        /^(?:yes|yeah|yep|looks good|confirm|confirm and develop|proceed|start|go ahead|approved?)\b/i.test(
          trimmed
        )
      ) {
        return {
          intent: 'confirm_intake',
          source: 'local_dev_analyzer',
          storyTitle: { value: null, provided: false, confidence: 0 },
          visualStyle: { value: null, provided: false, confidence: 0 },
          storyContext: { value: null, provided: false, confidence: 0 },
          missingFields: [],
          readyForGeneration: true,
        }
      }

      if (/^edit details$/i.test(trimmed)) {
        return {
          intent: 'request_edit',
          source: 'local_dev_analyzer',
          storyTitle: { value: null, provided: false, confidence: 0 },
          visualStyle: { value: null, provided: false, confidence: 0 },
          storyContext: { value: null, provided: false, confidence: 0 },
          missingFields: [],
          readyForGeneration: false,
        }
      }
    }

    // 4. General unrelated question during intake (preserve state)
    const generalAnswer = detectGeneralQuestion(trimmed)
    if (generalAnswer) {
      return {
        intent: 'general_question',
        source: 'local_dev_analyzer',
        storyTitle: { value: null, provided: false, confidence: 0 },
        visualStyle: { value: null, provided: false, confidence: 0 },
        storyContext: { value: null, provided: false, confidence: 0 },
        missingFields: currentState.missingFields,
        readyForGeneration: false,
        generalAnswer,
      }
    }

    // 5. Extract fields from natural language
    const extractedTitle = extractTitleFromText(trimmed, pendingField)
    const extractedStyle = extractVisualStyleFromText(trimmed, pendingField)
    const extractedContext = extractStoryContextFromText(trimmed, pendingField)

    // 6. Determine intent (modification vs adding context vs answering vs creating)
    let intent: IntakeIntent = 'create_story'
    if (
      currentState.storyTitle.provided &&
      extractedTitle.provided &&
      /(?:change|rename|update|actually)/i.test(trimmed)
    ) {
      intent = 'modify_story_title'
    } else if (
      currentState.visualStyle.provided &&
      extractedStyle.provided &&
      /(?:change|switch|update|actually|instead)/i.test(trimmed)
    ) {
      intent = 'modify_visual_style'
    } else if (
      currentState.storyContext.provided &&
      extractedContext.provided &&
      /(?:change|update|actually|instead)/i.test(trimmed)
    ) {
      intent = 'modify_story_context'
    } else if (
      currentState.storyContext.provided &&
      extractedContext.provided &&
      /^(?:also|plus|and\s+also|additionally)\b/i.test(trimmed)
    ) {
      intent = 'add_context'
    } else if (pendingField !== null) {
      intent = 'answer_question'
    }

    // Check for ambiguous response when answering a pending question with nothing extracted
    let ambiguousReason: string | null = null
    if (
      pendingField !== null &&
      !extractedTitle.provided &&
      !extractedStyle.provided &&
      !extractedContext.provided
    ) {
      ambiguousReason =
        pendingField === 'story_context'
          ? 'Could you share a bit more detail about the central character, conflict, or situation?'
          : pendingField === 'visual_style'
          ? 'Could you clarify the visual medium, lighting, or aesthetic you imagine (for example, anime, cinematic realism, or dark fantasy)?'
          : 'Could you share the exact title you would like to use, or ask me to suggest a few?'
    }

    const nextMissing = computeMissingFields(
      Boolean(extractedTitle.provided || currentState.storyTitle.provided),
      Boolean(extractedStyle.provided || currentState.visualStyle.provided),
      Boolean(extractedContext.provided || currentState.storyContext.provided)
    )

    return {
      intent,
      source: 'local_dev_analyzer',
      storyTitle: extractedTitle,
      visualStyle: extractedStyle,
      storyContext: extractedContext,
      missingFields: nextMissing,
      readyForGeneration: nextMissing.length === 0,
      ambiguousReason,
    }
  }
}

/**
 * Production analyzer that delegates structured extraction to the FastAPI LLM
 * endpoint (/api/v1/ai/intake/analyze) and transparently falls back to
 * LocalDevStoryIntakeAnalyzer when the backend or OpenAI key is unavailable.
 */
export class HybridStoryIntakeAnalyzer implements StoryIntakeAnalyzer {
  private readonly fallback = new LocalDevStoryIntakeAnalyzer()

  async analyze(input: AnalyzeIntakeInput): Promise<IntakeAnalysisResult> {
    if (typeof fetch === 'undefined' || import.meta.env.MODE === 'test') {
      return this.fallback.analyze(input)
    }

    try {
      const res = await fetch(`${BASE_URL}/api/v1/ai/intake/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input.message,
          current_state: {
            story_title: input.currentState.storyTitle.value,
            visual_style: input.currentState.visualStyle.value,
            story_context: input.currentState.storyContext.value,
            current_question: input.currentState.currentQuestion,
            status: input.currentState.status,
          },
          recent_history: input.recentHistory ?? [],
        }),
      })

      if (!res.ok) {
        return this.fallback.analyze(input)
      }

      const data = (await res.json()) as {
        analysis?: {
          intent?: IntakeIntent
          extracted_fields?: {
            story_title?: { value?: string | null; confidence?: number }
            visual_style?: {
              value?: string | null
              confidence?: number
              details?: VisualDetails
            }
            story_context?: {
              value?: string | null
              confidence?: number
              theme?: string | null
              main_conflict?: string | null
            }
          }
          missing_fields?: IntakeFieldKey[]
        }
        conversation?: {
          assistant_message?: string | null
        }
        intent?: IntakeIntent
        extracted_fields?: {
          story_title?: { value?: string | null; confidence?: number }
          visual_style?: {
            value?: string | null
            confidence?: number
            details?: VisualDetails
          }
          story_context?: {
            value?: string | null
            confidence?: number
            theme?: string | null
            main_conflict?: string | null
          }
        }
        missing_fields?: IntakeFieldKey[]
        general_answer?: string | null
      }

      const analysisBlock = data.analysis ?? data
      const st = analysisBlock.extracted_fields?.story_title
      const vs = analysisBlock.extracted_fields?.visual_style
      const sc = analysisBlock.extracted_fields?.story_context

      const sanitizeField = (val: string | null | undefined): string | null => {
        const cleaned = val?.trim()
        if (!cleaned) return null
        if (/^(null|none|n\/a|na|undefined|untitled|give me a story|i want a story)$/i.test(cleaned)) {
          return null
        }
        return cleaned
      }

      let titleVal = sanitizeField(st?.value)
      const styleVal = sanitizeField(vs?.value)
      let ctxVal = sanitizeField(sc?.value)

      // Guard: never accept an LLM-invented title that does not appear in the user's message
      // unless the user was directly answering the story_title question.
      if (
        titleVal &&
        input.currentState.currentQuestion !== 'story_title' &&
        !input.message.toLowerCase().includes(titleVal.toLowerCase())
      ) {
        titleVal = null
      }

      // Guard: never accept hallucinated context for generic "give me a story" / "I want an anime story" requests
      if (
        ctxVal &&
        /^(?:give me|i want|tell me|create|make|write)\s+(?:a|an)\s+(?:[a-z-\s]{0,24}\s+)?story[.!?]*$/i.test(
          input.message.trim()
        )
      ) {
        ctxVal = null
      }

      const missing = computeMissingFields(
        Boolean(titleVal || input.currentState.storyTitle.provided),
        Boolean(styleVal || input.currentState.visualStyle.provided),
        Boolean(ctxVal || input.currentState.storyContext.provided)
      )

      const safeAssistantMessage = sanitizeAssistantMessage(
        data.conversation?.assistant_message
      )

      return {
        intent: analysisBlock.intent ?? 'create_story',
        source: 'backend_llm',
        storyTitle: {
          value: titleVal,
          provided: Boolean(titleVal),
          confidence: st?.confidence ?? (titleVal ? 0.9 : 0),
        },
        visualStyle: {
          value: styleVal,
          provided: Boolean(styleVal),
          confidence: vs?.confidence ?? (styleVal ? 0.9 : 0),
          details: vs?.details,
        },
        storyContext: {
          value: ctxVal,
          provided: Boolean(ctxVal),
          confidence: sc?.confidence ?? (ctxVal ? 0.9 : 0),
          theme: sc?.theme ?? null,
          mainConflict: sc?.main_conflict ?? null,
        },
        missingFields: analysisBlock.missing_fields ?? missing,
        readyForGeneration: missing.length === 0,
        assistantMessage: safeAssistantMessage,
        generalAnswer: sanitizeAssistantMessage(data.general_answer),
      }
    } catch {
      return this.fallback.analyze(input)
    }
  }
}
