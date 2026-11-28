import { sendAIChat, type AIChatResponse } from '@/lib/api'
import { buildSimulatedAiReply } from '@/lib/mockAi'
import type { ChatMessage, Conversation } from '@/types/chat'
import type { StoryIntakeState } from '../types/storyIntake.types'

export class IntakeNotConfirmedError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'IntakeNotConfirmedError'
  }
}

/**
 * Independent validation gate inside the story generation service.
 * Ensures story generation can never run unless Title, Visual Style,
 * and Story Context are all provided and explicitly confirmed by the creator.
 */
export function validateIntakeReadyForGeneration(
  intakeState: StoryIntakeState | null | undefined
): asserts intakeState is StoryIntakeState {
  if (!intakeState) {
    throw new IntakeNotConfirmedError(
      'Story intake state is missing. Collect and confirm title, visual style, and story context first.'
    )
  }

  if (!intakeState.storyTitle.provided || !intakeState.storyTitle.value?.trim()) {
    throw new IntakeNotConfirmedError('Cannot generate story: story_title is missing.')
  }
  if (!intakeState.visualStyle.provided || !intakeState.visualStyle.value?.trim()) {
    throw new IntakeNotConfirmedError('Cannot generate story: visual_style is missing.')
  }
  if (!intakeState.storyContext.provided || !intakeState.storyContext.value?.trim()) {
    throw new IntakeNotConfirmedError('Cannot generate story: story_context is missing.')
  }

  if (
    !intakeState.storyTitle.confirmed ||
    !intakeState.visualStyle.confirmed ||
    !intakeState.storyContext.confirmed ||
    (intakeState.status !== 'ready_for_generation' && intakeState.status !== 'completed')
  ) {
    throw new IntakeNotConfirmedError(
      'Cannot generate story before explicit creator confirmation.'
    )
  }
}

export type StoryGenerationRunner = (params: {
  conversation: Conversation
  intakeState: StoryIntakeState
}) => Promise<AIChatResponse>

let customRunner: StoryGenerationRunner | null = null

export function setStoryGenerationRunner(runner: StoryGenerationRunner | null): void {
  customRunner = runner
}

export const defaultStoryGenerationRunner: StoryGenerationRunner = async ({
  conversation,
  intakeState,
}) => {
  const historyForAI = conversation.messages
    .filter((m: ChatMessage) => m.role === 'user' || m.role === 'assistant')
    .slice(-20)
    .map((m: ChatMessage) => ({ role: m.role as 'user' | 'assistant', content: m.content }))

  const enrichedDraft: Record<string, unknown> = {
    ...conversation.storyDraft,
    title: intakeState.storyTitle.value,
    visualStyle: intakeState.visualStyle.value,
    premise: intakeState.storyContext.value,
  }

  try {
    return await sendAIChat({
      messages: historyForAI,
      interview_step:
        conversation.interviewStep === 'idle' ? 'ready_for_plan' : conversation.interviewStep,
      story_draft: enrichedDraft,
      intake_state: {
        story_title: intakeState.storyTitle.value,
        visual_style: intakeState.visualStyle.value,
        story_context: intakeState.storyContext.value,
        status: intakeState.status,
        confirmed: true,
      },
    })
  } catch {
    // Graceful local fallback ONLY after intake has been validated and confirmed
    const simulated = buildSimulatedAiReply(
      {
        ...conversation,
        interviewStep: 'idle',
        storyDraft: {
          ...conversation.storyDraft,
          title: intakeState.storyTitle.value ?? 'Untitled',
          visualStyle: intakeState.visualStyle.value ?? undefined,
          premise: intakeState.storyContext.value ?? '',
        },
      },
      `Develop the story "${intakeState.storyTitle.value}" in ${intakeState.visualStyle.value} style: ${intakeState.storyContext.value}`
    )

    return {
      content: simulated.assistantMessage.content,
      next_step: simulated.nextStep,
      options: simulated.assistantMessage.options ?? null,
      planner: simulated.generatedPlanner ?? null,
      suggested_title: intakeState.storyTitle.value,
    }
  }
}

export async function generateConfirmedStory(params: {
  conversation: Conversation
  intakeState: StoryIntakeState
}): Promise<AIChatResponse> {
  validateIntakeReadyForGeneration(params.intakeState)
  const runner = customRunner ?? defaultStoryGenerationRunner
  return runner(params)
}
