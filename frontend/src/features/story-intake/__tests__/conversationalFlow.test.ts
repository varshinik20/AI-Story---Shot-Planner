import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from '@/store/chatStore'
import {
  HybridStoryIntakeAnalyzer,
  LocalDevStoryIntakeAnalyzer,
  sanitizeAssistantMessage,
} from '../services/storyIntakeAnalyzer'
import { StoryIntakeService, createInitialIntakeState } from '../services/storyIntakeService'
import { storyIntakePersistence } from '../services/storyIntakePersistence'
import { setStoryGenerationRunner } from '../services/storyGenerationService'

const FORBIDDEN_INTERNAL_PATTERNS = [
  /\bthe user\b/i,
  /\buser wants\b/i,
  /\buser asks\b/i,
  /\bmissing_fields\b/i,
  /\bstory_title\b/i,
  /\bvisual_style\b/i,
  /\bstory_context\b/i,
  /\bnext_action\b/i,
  /missing field:/i,
]

function assertNaturalConversationResponse(text: string): void {
  expect(text.trim().length).toBeGreaterThan(10)
  expect(text.trim().startsWith('{')).toBe(false)
  for (const pat of FORBIDDEN_INTERNAL_PATTERNS) {
    expect(text).not.toMatch(pat)
  }
}

describe('Conversational AI Quality & Leak Prevention', () => {
  const mockGenerator = vi.fn()

  beforeEach(() => {
    window.localStorage.clear()
    storyIntakePersistence.clearAll()
    useChatStore.getState().resetDemoData()
    mockGenerator.mockReset()
    mockGenerator.mockResolvedValue({
      content: 'Story development started.',
      next_step: 'relationship',
      options: null,
      planner: null,
      suggested_title: null,
    })
    setStoryGenerationRunner(mockGenerator)
  })

  afterEach(() => {
    setStoryGenerationRunner(null)
    vi.unstubAllGlobals()
  })

  it('matches the natural multi-turn Section 4 conversation without leaking internal analysis or generating early', async () => {
    const store = useChatStore.getState()

    // Turn 1: "Tell me a story."
    const convId = await store.sendMessage('Tell me a story.')
    let conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    const reply1 = conv.messages[conv.messages.length - 1].content
    assertNaturalConversationResponse(reply1)
    expect(reply1).toMatch(/title/i)
    expect(reply1).toMatch(/suggest/i)
    expect(mockGenerator).not.toHaveBeenCalled()

    // Turn 2: "The Shadow Within."
    await store.sendMessage('The Shadow Within.', undefined, convId)
    conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    const reply2 = conv.messages[conv.messages.length - 1].content
    assertNaturalConversationResponse(reply2)
    expect(conv.intakeState?.storyTitle.value).toBe('The Shadow Within')
    expect(reply2).toMatch(/visual/i)
    expect(mockGenerator).not.toHaveBeenCalled()

    // Turn 3: "Dark fantasy."
    await store.sendMessage('Dark fantasy.', undefined, convId)
    conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    const reply3 = conv.messages[conv.messages.length - 1].content
    assertNaturalConversationResponse(reply3)
    expect(conv.intakeState?.visualStyle.value).toBe('Dark fantasy')
    expect(reply3).toMatch(/The Shadow Within/)
    expect(reply3).toMatch(/rough idea|happening|story/i)
    expect(mockGenerator).not.toHaveBeenCalled()

    // Turn 4: "A girl discovers that her shadow is alive."
    await store.sendMessage('A girl discovers that her shadow is alive.', undefined, convId)
    conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    const reply4 = conv.messages[conv.messages.length - 1].content
    assertNaturalConversationResponse(reply4)
    expect(conv.intakeState?.status).toBe('awaiting_confirmation')
    expect(reply4).toMatch(/The Shadow Within/)
    expect(reply4).toMatch(/dark fantasy/i)
    expect(reply4).toMatch(/shadow is alive/i)
    expect(reply4).toMatch(/shall we start building/i)
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('passes all 8 required Section 11 test messages naturally and without premature generation', async () => {
    const store = useChatStore.getState()

    // 1. "Tell me a story."
    const c1 = await store.sendMessage('Tell me a story.')
    const conv1 = useChatStore.getState().conversations.find((c) => c.id === c1)!
    assertNaturalConversationResponse(conv1.messages[conv1.messages.length - 1].content)
    expect(conv1.intakeState?.currentQuestion).toBe('story_title')

    // 2. "I want an anime story."
    store.createNewChat()
    const c2 = await store.sendMessage('I want an anime story.')
    const conv2 = useChatStore.getState().conversations.find((c) => c.id === c2)!
    assertNaturalConversationResponse(conv2.messages[conv2.messages.length - 1].content)
    expect(conv2.intakeState?.visualStyle.value).toBe('Anime')
    expect(conv2.intakeState?.currentQuestion).toBe('story_title')

    // 3. "Create The Shadow Within."
    store.createNewChat()
    const c3 = await store.sendMessage('Create The Shadow Within.')
    const conv3 = useChatStore.getState().conversations.find((c) => c.id === c3)!
    assertNaturalConversationResponse(conv3.messages[conv3.messages.length - 1].content)
    expect(conv3.intakeState?.storyTitle.value).toBe('The Shadow Within')
    expect(conv3.intakeState?.currentQuestion).toBe('visual_style')

    // 4. "I want a dark fantasy story about a girl."
    store.createNewChat()
    const c4 = await store.sendMessage('I want a dark fantasy story about a girl.')
    const conv4 = useChatStore.getState().conversations.find((c) => c.id === c4)!
    assertNaturalConversationResponse(conv4.messages[conv4.messages.length - 1].content)
    expect(conv4.intakeState?.visualStyle.value).toBe('Dark fantasy')
    expect(conv4.intakeState?.storyContext.value).toMatch(/girl/i)
    expect(conv4.intakeState?.currentQuestion).toBe('story_title')

    // 5. "Create The Last Light, a dark fantasy story about a girl saving her village."
    store.createNewChat()
    const c5 = await store.sendMessage(
      'Create The Last Light, a dark fantasy story about a girl saving her village.'
    )
    const conv5 = useChatStore.getState().conversations.find((c) => c.id === c5)!
    assertNaturalConversationResponse(conv5.messages[conv5.messages.length - 1].content)
    expect(conv5.intakeState?.storyTitle.value).toBe('The Last Light')
    expect(conv5.intakeState?.visualStyle.value).toBe('Dark fantasy')
    expect(conv5.intakeState?.storyContext.value).toMatch(/girl saving her village/i)
    expect(conv5.intakeState?.status).toBe('awaiting_confirmation')

    // 6. "Actually, change the style to cinematic realism."
    await store.sendMessage('Actually, change the style to cinematic realism.', undefined, c5)
    const conv5Updated = useChatStore.getState().conversations.find((c) => c.id === c5)!
    assertNaturalConversationResponse(
      conv5Updated.messages[conv5Updated.messages.length - 1].content
    )
    expect(conv5Updated.intakeState?.visualStyle.value).toBe('Cinematic realism')
    expect(conv5Updated.intakeState?.storyTitle.value).toBe('The Last Light')
    expect(conv5Updated.intakeState?.status).toBe('awaiting_confirmation')

    // 7. "I don't have a title. Suggest some."
    store.createNewChat()
    const c7 = await store.sendMessage("I don't have a title. Suggest some.")
    const conv7 = useChatStore.getState().conversations.find((c) => c.id === c7)!
    const reply7 = conv7.messages[conv7.messages.length - 1]
    assertNaturalConversationResponse(reply7.content)
    expect(conv7.intakeState?.storyTitle.provided).toBe(false)
    expect(reply7.options?.length).toBeGreaterThanOrEqual(3)

    // 8. "Let me explain the story first."
    store.createNewChat()
    const c8 = await store.sendMessage('Let me explain the story first.')
    const conv8 = useChatStore.getState().conversations.find((c) => c.id === c8)!
    const reply8 = conv8.messages[conv8.messages.length - 1].content
    assertNaturalConversationResponse(reply8)
    expect(conv8.intakeState?.currentQuestion).toBe('story_context')
    expect(reply8).toMatch(/about|idea/i)

    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('blocks third-person internal analysis and raw JSON returned by backend LLM', async () => {
    expect(
      sanitizeAssistantMessage(
        'The user asks for a story without specifying a title, visual style, or premise.'
      )
    ).toBeNull()
    expect(sanitizeAssistantMessage('{"intent":"create_story"}')).toBeNull()
    expect(sanitizeAssistantMessage('Missing field: visual_style.')).toBeNull()
    expect(
      sanitizeAssistantMessage(
        "Of course! I'd love to help you create one. What would you like to name it?"
      )
    ).toBe("Of course! I'd love to help you create one. What would you like to name it?")

    // Even if the backend returns third-person internal analysis in conversation.assistant_message,
    // StoryIntakeService must sanitize it and render a natural conversational question instead.
    const service = new StoryIntakeService(new LocalDevStoryIntakeAnalyzer())
    const state = createInitialIntakeState('conv_leak', 'proj_1')

    const spyAnalyzer = {
      async analyze() {
        return {
          intent: 'create_story' as const,
          source: 'backend_llm' as const,
          storyTitle: { value: null, provided: false, confidence: 0 },
          visualStyle: { value: null, provided: false, confidence: 0 },
          storyContext: { value: null, provided: false, confidence: 0 },
          missingFields: ['story_title', 'visual_style', 'story_context'] as Array<
            'story_title' | 'visual_style' | 'story_context'
          >,
          readyForGeneration: false,
          assistantMessage: sanitizeAssistantMessage(
            'The user asks for a story without specifying a title, visual style, or premise.'
          ),
        }
      },
    }

    const guardedService = new StoryIntakeService(spyAnalyzer)
    const turn = await guardedService.processUserMessage({
      conversationId: 'conv_leak',
      projectId: 'proj_1',
      currentState: state,
      message: 'Tell me a story.',
    })

    assertNaturalConversationResponse(turn.assistantContent)
    expect(turn.assistantContent).toMatch(/title/i)
    expect(HybridStoryIntakeAnalyzer).toBeDefined()
    expect(service).toBeDefined()
  })
})
