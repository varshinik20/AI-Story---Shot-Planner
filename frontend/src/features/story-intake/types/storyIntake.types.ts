export type IntakeFieldKey = 'story_title' | 'visual_style' | 'story_context'

export type IntakeStatus =
  | 'collecting'
  | 'awaiting_confirmation'
  | 'ready_for_generation'
  | 'generating'
  | 'completed'

export type IntakeIntent =
  | 'create_story'
  | 'answer_question'
  | 'modify_story_title'
  | 'modify_visual_style'
  | 'modify_story_context'
  | 'add_context'
  | 'confirm_intake'
  | 'request_edit'
  | 'suggest_title'
  | 'explain_story_first'
  | 'general_question'
  | 'story_upload'
  | 'story_continuation'

export interface VisualDetails {
  lighting?: string
  mood?: string
  medium?: string
  palette?: string
  [key: string]: string | undefined
}

export interface StoryIntakeState {
  projectId: string
  conversationId: string

  storyTitle: {
    value: string | null
    provided: boolean
    confirmed: boolean
  }

  visualStyle: {
    value: string | null
    provided: boolean
    confirmed: boolean
    details?: VisualDetails
  }

  storyContext: {
    value: string | null
    provided: boolean
    confirmed: boolean
    theme?: string | null
    mainConflict?: string | null
  }

  missingFields: IntakeFieldKey[]
  currentQuestion: IntakeFieldKey | null
  status: IntakeStatus
  awaitingConfirmation: boolean
  generationStarted: boolean
  updatedAt: number
}

export interface ExtractedFieldValue<TDetails = undefined> {
  value: string | null
  provided: boolean
  confidence: number
  details?: TDetails
}

export interface ExtractedContextValue {
  value: string | null
  provided: boolean
  confidence: number
  theme?: string | null
  mainConflict?: string | null
}

export interface IntakeAnalysisResult {
  intent: IntakeIntent
  source: 'backend_llm' | 'local_dev_analyzer'
  storyTitle: ExtractedFieldValue
  visualStyle: ExtractedFieldValue<VisualDetails>
  storyContext: ExtractedContextValue
  missingFields: IntakeFieldKey[]
  readyForGeneration: boolean
  assistantMessage?: string | null
  ambiguousReason?: string | null
  generalAnswer?: string | null
}

export interface AnalyzeIntakeInput {
  message: string
  currentState: StoryIntakeState
  hasAttachment?: boolean
  attachmentName?: string
  recentHistory?: Array<{ role: 'user' | 'assistant'; content: string }>
}

export interface StoryIntakeAnalyzer {
  analyze(input: AnalyzeIntakeInput): Promise<IntakeAnalysisResult>
}

export interface QuestionSelectionResult {
  nextField: IntakeFieldKey | null
  questionText: string
  includeStyleSuggestions: boolean
  suggestedTitles?: string[]
}

export interface IntakeTurnResponse {
  state: StoryIntakeState
  assistantContent: string
  includeStyleSuggestions: boolean
  showConfirmationCard: boolean
  titleOptions?: string[]
  shouldHandoffToGeneration: boolean
  analysis: IntakeAnalysisResult
}
