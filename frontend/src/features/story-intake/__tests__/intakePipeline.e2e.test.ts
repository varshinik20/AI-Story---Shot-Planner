import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from '@/store/chatStore'
import { storyIntakePersistence } from '../services/storyIntakePersistence'
import {
  IntakeNotConfirmedError,
  generateConfirmedStory,
  setStoryGenerationRunner,
  validateIntakeReadyForGeneration,
} from '../services/storyGenerationService'
import { createInitialIntakeState } from '../services/storyIntakeService'

describe('StoryForge Full Execution Pipeline (sendMessage -> Intake -> Confirmation Gate -> Generation)', () => {
  const mockGenerator = vi.fn()

  beforeEach(() => {
    window.localStorage.clear()
    storyIntakePersistence.clearAll()
    useChatStore.getState().resetDemoData()
    mockGenerator.mockReset()
    mockGenerator.mockResolvedValue({
      content: 'Story development started for your confirmed brief.',
      next_step: 'relationship',
      options: null,
      planner: null,
      suggested_title: null,
    })
    setStoryGenerationRunner(mockGenerator)
  })

  afterEach(() => {
    setStoryGenerationRunner(null)
  })

  it('CASE 1: "give me a story" asks for story title and NEVER generates a story or invents "The Last Stop"', async () => {
    const convId = await useChatStore.getState().sendMessage('give me a story')

    const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    const reply = conv.messages[conv.messages.length - 1]

    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.title).toBe('New Story')
    expect(conv.storyDraft.title).toBe('')
    expect(conv.intakeState?.storyTitle.value).toBeNull()
    expect(conv.intakeState?.visualStyle.value).toBeNull()
    expect(conv.intakeState?.storyContext.value).toBeNull()
    expect(conv.intakeState?.status).toBe('collecting')
    expect(conv.intakeState?.generationStarted).toBe(false)
    expect(reply.content).toMatch(/title/i)
    expect(reply.content).not.toMatch(/The Last Stop/i)
    expect(reply.content).not.toMatch(/the user/i)
  })

  it('CASE 2: "I want a story" asks for story title without generating', async () => {
    const convId = await useChatStore.getState().sendMessage('I want a story')
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    const reply = conv.messages[conv.messages.length - 1]

    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.intakeState?.currentQuestion).toBe('story_title')
    expect(reply.content).toMatch(/title/i)
  })

  it('CASE 3: "I want an anime story" extracts Anime and asks for story title without generating', async () => {
    const convId = await useChatStore.getState().sendMessage('I want an anime story')
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!

    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.intakeState?.visualStyle.value).toBe('Anime')
    expect(conv.intakeState?.storyTitle.value).toBeNull()
    expect(conv.intakeState?.currentQuestion).toBe('story_title')
  })

  it('CASE 4: "Create a story called The Shadow Within" extracts Title and asks for visual style', async () => {
    const convId = await useChatStore
      .getState()
      .sendMessage('Create a story called The Shadow Within')
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    const reply = conv.messages[conv.messages.length - 1]

    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.intakeState?.storyTitle.value).toBe('The Shadow Within')
    expect(conv.intakeState?.currentQuestion).toBe('visual_style')
    expect(reply.showStyleSuggestions).toBe(true)
  })

  it('CASE 5: "Create a dark fantasy story" extracts Dark fantasy and asks for title', async () => {
    const convId = await useChatStore
      .getState()
      .sendMessage('Create a dark fantasy story')
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!

    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.intakeState?.visualStyle.value).toBe('Dark fantasy')
    expect(conv.intakeState?.currentQuestion).toBe('story_title')
  })

  it('CASE 6: "Create a story about a girl who discovers a mysterious shadow" extracts context and asks for title', async () => {
    const convId = await useChatStore
      .getState()
      .sendMessage('Create a story about a girl who discovers a mysterious shadow')
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!

    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.intakeState?.storyContext.value).toMatch(
      /girl who discovers a mysterious shadow/i
    )
    expect(conv.intakeState?.storyTitle.value).toBeNull()
    expect(conv.intakeState?.currentQuestion).toBe('story_title')
  })

  it('CASE 7: "Create The Last Light, an anime story" extracts Title + Visual style and asks for context', async () => {
    const convId = await useChatStore
      .getState()
      .sendMessage('Create The Last Light, an anime story')
    const conv = useChatStore.getState().conversations.find((c) => c.id === convId)!

    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.intakeState?.storyTitle.value).toBe('The Last Light')
    expect(conv.intakeState?.visualStyle.value).toBe('Anime')
    expect(conv.intakeState?.currentQuestion).toBe('story_context')
  })

  it('CASE 8 & CASE 9: All three fields -> confirmation gate -> "Yes, proceed." invokes story generation exactly once', async () => {
    const convId = await useChatStore
      .getState()
      .sendMessage(
        'Create The Last Light, a dark fantasy story about a girl saving her village after the sun disappears'
      )

    let conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    expect(mockGenerator).not.toHaveBeenCalled()
    expect(conv.intakeState?.status).toBe('awaiting_confirmation')
    expect(conv.intakeState?.awaitingConfirmation).toBe(true)
    expect(conv.intakeState?.generationStarted).toBe(false)
    const summaryMsg = conv.messages[conv.messages.length - 1]
    expect(summaryMsg.intakeConfirmation).toBeDefined()
    expect(summaryMsg.content).toMatch(/The Last Light/i)
    expect(summaryMsg.content).toMatch(/dark fantasy/i)
    expect(summaryMsg.content).toMatch(/girl saving her village/i)

    // CASE 9: Explicit user confirmation invokes story generation exactly once
    await useChatStore.getState().sendMessage('Yes, proceed.', undefined, convId)

    conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    expect(mockGenerator).toHaveBeenCalledTimes(1)
    expect(conv.intakeState?.status).toBe('completed')
    expect(conv.intakeState?.generationStarted).toBe(true)
    expect(conv.intakeState?.storyTitle.confirmed).toBe(true)

    // Subsequent message in the confirmed story continues story development normally
    await useChatStore
      .getState()
      .sendMessage('Make Scene 1 start at dusk.', undefined, convId)
    expect(mockGenerator).toHaveBeenCalledTimes(2)
  })

  it('Section 6 multi-turn conversation: Give me a story -> The Shadow Within -> Dark fantasy -> context -> Yes, proceed', async () => {
    const store = useChatStore.getState()

    const convId = await store.sendMessage('Give me a story.')
    expect(mockGenerator).not.toHaveBeenCalled()

    await store.sendMessage('The Shadow Within.', undefined, convId)
    let conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    expect(conv.intakeState?.storyTitle.value).toBe('The Shadow Within')
    expect(conv.intakeState?.currentQuestion).toBe('visual_style')
    expect(mockGenerator).not.toHaveBeenCalled()

    await store.sendMessage('Dark fantasy.', undefined, convId)
    conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    expect(conv.intakeState?.visualStyle.value).toBe('Dark fantasy')
    expect(conv.intakeState?.currentQuestion).toBe('story_context')
    expect(mockGenerator).not.toHaveBeenCalled()

    await store.sendMessage('A girl discovers that her shadow is alive.', undefined, convId)
    conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    expect(conv.intakeState?.status).toBe('awaiting_confirmation')
    expect(conv.intakeState?.awaitingConfirmation).toBe(true)
    expect(mockGenerator).not.toHaveBeenCalled()

    await store.sendMessage('Yes, proceed.', undefined, convId)
    conv = useChatStore.getState().conversations.find((c) => c.id === convId)!
    expect(mockGenerator).toHaveBeenCalledTimes(1)
    expect(conv.intakeState?.status).toBe('completed')
  })

  it('independently rejects story generation if intake state is incomplete or unconfirmed', async () => {
    const incomplete = createInitialIntakeState('conv_x', 'proj_1')
    expect(() => validateIntakeReadyForGeneration(incomplete)).toThrow(
      IntakeNotConfirmedError
    )

    const unconfirmed = {
      ...incomplete,
      storyTitle: { value: 'Title', provided: true, confirmed: false },
      visualStyle: { value: 'Anime', provided: true, confirmed: false },
      storyContext: { value: 'A premise about trust.', provided: true, confirmed: false },
      missingFields: [],
      status: 'awaiting_confirmation' as const,
      awaitingConfirmation: true,
    }

    await expect(
      generateConfirmedStory({
        conversation: {
          id: 'conv_x',
          title: 'Title',
          projectId: 'proj_1',
          createdAt: Date.now(),
          updatedAt: Date.now(),
          messages: [],
          storyDraft: { title: 'Title', premise: '', segments: [] },
          interviewStep: 'idle',
          intakeState: unconfirmed,
        },
        intakeState: unconfirmed,
      })
    ).rejects.toThrow(IntakeNotConfirmedError)
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('does not share intake state between multiple conversations and catches stale conversations without intakeState', async () => {
    // Seed a legacy conversation without intakeState (simulating pre-update localStorage)
    useChatStore.setState((s) => ({
      conversations: [
        {
          id: 'legacy_conv',
          title: 'Legacy Chat',
          projectId: 'proj_my_stories',
          createdAt: Date.now(),
          updatedAt: Date.now(),
          messages: [],
          storyDraft: { title: '', premise: '', segments: [] },
          interviewStep: 'idle',
        },
        ...s.conversations,
      ],
    }))

    await useChatStore.getState().sendMessage('give me a story', undefined, 'legacy_conv')
    const legacy = useChatStore.getState().conversations.find((c) => c.id === 'legacy_conv')!
    expect(mockGenerator).not.toHaveBeenCalled()
    expect(legacy.intakeState?.status).toBe('collecting')
    expect(legacy.intakeState?.currentQuestion).toBe('story_title')

    // Start a separate conversation with Anime style
    const secondId = await useChatStore.getState().sendMessage('I want an anime story')
    const second = useChatStore.getState().conversations.find((c) => c.id === secondId)!
    expect(second.intakeState?.visualStyle.value).toBe('Anime')
    expect(
      useChatStore.getState().conversations.find((c) => c.id === 'legacy_conv')?.intakeState
        ?.visualStyle.value
    ).toBeNull()
  })
})
