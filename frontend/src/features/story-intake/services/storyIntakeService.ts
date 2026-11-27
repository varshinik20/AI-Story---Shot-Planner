import type {
  AnalyzeIntakeInput,
  IntakeAnalysisResult,
  IntakeTurnResponse,
  StoryIntakeAnalyzer,
  StoryIntakeState,
} from '../types/storyIntake.types'
import {
  buildConfirmationSummaryText,
  buildTitleSuggestions,
  getMissingIntakeFields,
  selectNextQuestion,
} from './questionSelector'
import { HybridStoryIntakeAnalyzer, sanitizeAssistantMessage } from './storyIntakeAnalyzer'
import { storyIntakePersistence } from './storyIntakePersistence'

export function createInitialIntakeState(
  conversationId: string,
  projectId: string
): StoryIntakeState {
  return {
    projectId,
    conversationId,
    storyTitle: { value: null, provided: false, confirmed: false },
    visualStyle: { value: null, provided: false, confirmed: false },
    storyContext: { value: null, provided: false, confirmed: false },
    missingFields: ['story_title', 'visual_style', 'story_context'],
    currentQuestion: null,
    status: 'collecting',
    awaitingConfirmation: false,
    generationStarted: false,
    updatedAt: Date.now(),
  }
}

export class StoryIntakeService {
  constructor(private readonly analyzer: StoryIntakeAnalyzer) {}

  getOrCreateState(conversationId: string, projectId: string): StoryIntakeState {
    const saved = storyIntakePersistence.get(conversationId)
    if (saved) return saved
    const fresh = createInitialIntakeState(conversationId, projectId)
    storyIntakePersistence.save(fresh)
    return fresh
  }

  saveState(state: StoryIntakeState): void {
    storyIntakePersistence.save({ ...state, updatedAt: Date.now() })
  }

  async processUserMessage(
    input: Omit<AnalyzeIntakeInput, 'currentState'> & {
      conversationId: string
      projectId: string
      currentState?: StoryIntakeState
    }
  ): Promise<IntakeTurnResponse> {
    const baseState =
      input.currentState ?? this.getOrCreateState(input.conversationId, input.projectId)

    const analysis = await this.analyzer.analyze({
      message: input.message,
      currentState: baseState,
      hasAttachment: input.hasAttachment,
      attachmentName: input.attachmentName,
      recentHistory: input.recentHistory,
    })

    const nextState: StoryIntakeState = {
      ...baseState,
      storyTitle: { ...baseState.storyTitle },
      visualStyle: { ...baseState.visualStyle },
      storyContext: { ...baseState.storyContext },
      updatedAt: Date.now(),
    }

    // 1. Handle explicit confirmation
    if (analysis.intent === 'confirm_intake' && baseState.status === 'awaiting_confirmation') {
      if (baseState.generationStarted) {
        return {
          state: nextState,
          assistantContent: `Story development for **${nextState.storyTitle.value}** has already started.`,
          includeStyleSuggestions: false,
          showConfirmationCard: false,
          shouldHandoffToGeneration: false,
          analysis,
        }
      }
      nextState.storyTitle.confirmed = true
      nextState.visualStyle.confirmed = true
      nextState.storyContext.confirmed = true
      nextState.missingFields = []
      nextState.currentQuestion = null
      nextState.status = 'ready_for_generation'
      nextState.awaitingConfirmation = false
      nextState.generationStarted = true
      this.saveState(nextState)

      return {
        state: nextState,
        assistantContent: `Confirmed! Beginning story development for **${nextState.storyTitle.value}** in **${nextState.visualStyle.value}** style.`,
        includeStyleSuggestions: false,
        showConfirmationCard: false,
        shouldHandoffToGeneration: true,
        analysis,
      }
    }

    // 2. Handle edit request button or prompt while awaiting confirmation
    if (analysis.intent === 'request_edit') {
      nextState.status = 'collecting'
      nextState.awaitingConfirmation = false
      nextState.currentQuestion = null
      this.saveState(nextState)

      return {
        state: nextState,
        assistantContent:
          'Sure—tell me what you would like to change (for example, `"Change the title to ..."`, `"Change the style to ..."`, or update the story context), and I will keep all your other details intact.',
        includeStyleSuggestions: true,
        showConfirmationCard: false,
        shouldHandoffToGeneration: false,
        analysis,
      }
    }

    // 3. Handle title suggestion request without overwriting existing state
    if (analysis.intent === 'suggest_title') {
      const suggestions = buildTitleSuggestions(nextState)
      nextState.currentQuestion = 'story_title'
      nextState.status = 'collecting'
      this.saveState(nextState)

      return {
        state: nextState,
        assistantContent:
          'No problem at all! Here are a few title ideas to spark inspiration—pick one below or share your own:',
        includeStyleSuggestions: false,
        showConfirmationCard: false,
        titleOptions: suggestions,
        shouldHandoffToGeneration: false,
        analysis,
      }
    }

    // 3b. User asks to explain the story premise first before picking a title or style
    if (analysis.intent === 'explain_story_first') {
      nextState.currentQuestion = 'story_context'
      nextState.status = 'collecting'
      nextState.awaitingConfirmation = false
      this.saveState(nextState)

      return {
        state: nextState,
        assistantContent:
          "Of course! Tell me what your story is about—even a rough idea is great, and we'll shape the title and visual direction around it.",
        includeStyleSuggestions: false,
        showConfirmationCard: false,
        shouldHandoffToGeneration: false,
        analysis,
      }
    }

    // 4. Handle unrelated general question without discarding collected fields
    if (analysis.intent === 'general_question') {
      const selection = selectNextQuestion(nextState)
      const reminder = selection.questionText
      const answer =
        analysis.generalAnswer ||
        'I can help you plan your story, visual direction, and shot list step by step.'
      this.saveState(nextState)

      return {
        state: nextState,
        assistantContent: `${answer}\n\nWhenever you're ready to continue: ${reminder}`,
        includeStyleSuggestions: selection.includeStyleSuggestions,
        showConfirmationCard: nextState.status === 'awaiting_confirmation',
        shouldHandoffToGeneration: false,
        analysis,
      }
    }

    // 5. Apply newly extracted or modified fields (protecting already-collected info)
    const changedNotes: string[] = []

    if (analysis.storyTitle.provided && analysis.storyTitle.value) {
      const wasProvided = nextState.storyTitle.provided
      nextState.storyTitle = {
        value: analysis.storyTitle.value,
        provided: true,
        confirmed: false,
      }
      if (analysis.intent === 'modify_story_title' || wasProvided) {
        changedNotes.push(`Updated the story title to **${analysis.storyTitle.value}**.`)
      }
    }

    if (analysis.visualStyle.provided && analysis.visualStyle.value) {
      const wasProvided = nextState.visualStyle.provided
      nextState.visualStyle = {
        value: analysis.visualStyle.value,
        provided: true,
        confirmed: false,
        details: analysis.visualStyle.details ?? nextState.visualStyle.details,
      }
      if (analysis.intent === 'modify_visual_style' || wasProvided) {
        changedNotes.push(`Updated the visual style to **${analysis.visualStyle.value}**.`)
      }
    }

    if (analysis.storyContext.provided && analysis.storyContext.value) {
      const wasProvided = nextState.storyContext.provided
      if (analysis.intent === 'add_context' && nextState.storyContext.value) {
        const mergedContext = `${nextState.storyContext.value.replace(/\.$/, '')}. ${analysis.storyContext.value}`
        nextState.storyContext = {
          value: mergedContext,
          provided: true,
          confirmed: false,
          theme: analysis.storyContext.theme ?? nextState.storyContext.theme ?? null,
          mainConflict:
            analysis.storyContext.mainConflict ?? nextState.storyContext.mainConflict ?? null,
        }
        changedNotes.push('Added that detail to your story context.')
      } else {
        nextState.storyContext = {
          value: analysis.storyContext.value,
          provided: true,
          confirmed: false,
          theme: analysis.storyContext.theme ?? nextState.storyContext.theme ?? null,
          mainConflict:
            analysis.storyContext.mainConflict ?? nextState.storyContext.mainConflict ?? null,
        }
        if (analysis.intent === 'modify_story_context' || wasProvided) {
          changedNotes.push('Updated your story context.')
        }
      }
    }

    // 6. Recompute missing fields
    const missing = getMissingIntakeFields(nextState)
    nextState.missingFields = missing

    // 7. Handle ambiguous answer to a pending question with a natural clarification (never raw analysis)
    if (analysis.ambiguousReason && changedNotes.length === 0 && missing.length > 0) {
      nextState.status = 'collecting'
      this.saveState(nextState)
      const safeClarification =
        sanitizeAssistantMessage(analysis.ambiguousReason) ??
        selectNextQuestion(nextState).questionText
      return {
        state: nextState,
        assistantContent: safeClarification,
        includeStyleSuggestions: nextState.currentQuestion === 'visual_style',
        showConfirmationCard: false,
        shouldHandoffToGeneration: false,
        analysis,
      }
    }

    // 8. If all 3 fields are now collected -> move to awaiting_confirmation (do NOT generate story yet!)
    if (missing.length === 0) {
      nextState.currentQuestion = null
      nextState.status = 'awaiting_confirmation'
      nextState.awaitingConfirmation = true
      nextState.generationStarted = false
      this.saveState(nextState)

      const summary = buildConfirmationSummaryText(nextState)
      const safeLlmMessage =
        changedNotes.length === 0 ? sanitizeAssistantMessage(analysis.assistantMessage) : null
      const content =
        safeLlmMessage ??
        (changedNotes.length > 0 ? `${changedNotes.join(' ')}\n\n${summary}` : summary)

      return {
        state: nextState,
        assistantContent: content,
        includeStyleSuggestions: false,
        showConfirmationCard: true,
        shouldHandoffToGeneration: false,
        analysis,
      }
    }

    // 9. Ask only for the next missing field in warm, natural language
    const ackPrefix = changedNotes.length > 0 ? changedNotes.join(' ') : undefined
    const selection = selectNextQuestion(nextState, ackPrefix)
    nextState.currentQuestion = selection.nextField
    nextState.status = 'collecting'
    nextState.awaitingConfirmation = false
    this.saveState(nextState)

    const safeLlmQuestion =
      !ackPrefix ? sanitizeAssistantMessage(analysis.assistantMessage) : null

    return {
      state: nextState,
      assistantContent: safeLlmQuestion ?? selection.questionText,
      includeStyleSuggestions: selection.includeStyleSuggestions,
      showConfirmationCard: false,
      shouldHandoffToGeneration: false,
      analysis,
    }
  }

  markConfirmed(conversationId: string, projectId: string): StoryIntakeState {
    const state = this.getOrCreateState(conversationId, projectId)
    const confirmedState: StoryIntakeState = {
      ...state,
      storyTitle: { ...state.storyTitle, confirmed: true },
      visualStyle: { ...state.visualStyle, confirmed: true },
      storyContext: { ...state.storyContext, confirmed: true },
      missingFields: [],
      currentQuestion: null,
      status: 'completed',
      awaitingConfirmation: false,
      generationStarted: true,
      updatedAt: Date.now(),
    }
    this.saveState(confirmedState)
    return confirmedState
  }

  requestEdit(conversationId: string, projectId: string): StoryIntakeState {
    const state = this.getOrCreateState(conversationId, projectId)
    const editState: StoryIntakeState = {
      ...state,
      status: 'collecting',
      awaitingConfirmation: false,
      currentQuestion: null,
      updatedAt: Date.now(),
    }
    this.saveState(editState)
    return editState
  }

  markFieldEdit(
    conversationId: string,
    projectId: string,
    field: 'story_title' | 'visual_style' | 'story_context'
  ): StoryIntakeState {
    const state = this.getOrCreateState(conversationId, projectId)
    const editState: StoryIntakeState = {
      ...state,
      status: 'collecting',
      awaitingConfirmation: false,
      currentQuestion: field,
      updatedAt: Date.now(),
    }
    this.saveState(editState)
    return editState
  }
}

export const defaultStoryIntakeService = new StoryIntakeService(
  new HybridStoryIntakeAnalyzer()
)

export type { IntakeAnalysisResult }
