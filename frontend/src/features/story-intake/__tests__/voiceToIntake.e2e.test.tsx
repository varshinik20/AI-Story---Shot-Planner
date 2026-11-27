import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatComposer } from '@/components/chat/ChatComposer'
import { useChatStore } from '@/store/chatStore'
import { storyIntakePersistence } from '../services/storyIntakePersistence'
import { setStoryGenerationRunner } from '../services/storyGenerationService'
import type {
  SpeechRecognitionErrorEvent,
  SpeechRecognitionEvent,
  SpeechRecognitionInstance,
  SpeechRecognitionResult,
  SpeechRecognitionResultList,
} from '@/types/speech-recognition'

class MockVoiceEngine implements SpeechRecognitionInstance {
  static instances: MockVoiceEngine[] = []

  continuous = false
  interimResults = false
  lang = ''
  maxAlternatives = 1

  onstart: ((this: SpeechRecognitionInstance, ev: Event) => void) | null = null
  onresult: ((this: SpeechRecognitionInstance, ev: SpeechRecognitionEvent) => void) | null = null
  onerror:
    | ((this: SpeechRecognitionInstance, ev: SpeechRecognitionErrorEvent) => void)
    | null = null
  onend: ((this: SpeechRecognitionInstance, ev: Event) => void) | null = null

  private latestItems: Array<{ transcript: string; isFinal: boolean }> = []

  constructor() {
    MockVoiceEngine.instances.push(this)
  }

  addEventListener(): void {}
  removeEventListener(): void {}
  dispatchEvent(): boolean {
    return true
  }

  start(): void {
    this.onstart?.call(this, new Event('start'))
  }

  stop(): void {
    // Simulate browser finalizing pending speech results during shutdown before onend
    if (this.latestItems.some((item) => !item.isFinal)) {
      const finalized = this.latestItems.map((item) => ({ ...item, isFinal: true }))
      this.emitResult(finalized)
    }
    this.onend?.call(this, new Event('end'))
  }

  abort(): void {}

  emitResult(items: Array<{ transcript: string; isFinal: boolean }>): void {
    this.latestItems = items
    const resultObjs: SpeechRecognitionResult[] = items.map((item) => {
      const alt = { transcript: item.transcript, confidence: 0.96 }
      return {
        isFinal: item.isFinal,
        length: 1,
        item: () => alt,
        0: alt,
      }
    })
    const results: SpeechRecognitionResultList = {
      length: resultObjs.length,
      item: (index: number) => resultObjs[index],
      ...Object.fromEntries(resultObjs.map((r, i) => [i, r])),
    } as SpeechRecognitionResultList
    this.onresult?.call(this, { resultIndex: 0, results } as SpeechRecognitionEvent)
  }

  emitError(code: string): void {
    this.onerror?.call(this, { error: code, message: code } as SpeechRecognitionErrorEvent)
  }

  emitUnexpectedEnd(): void {
    this.onend?.call(this, new Event('end'))
  }
}

async function speakAndSubmit(transcripts: Array<{ transcript: string; isFinal: boolean }>) {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Start voice input' }))
  })
  const engine = MockVoiceEngine.instances[MockVoiceEngine.instances.length - 1]
  act(() => {
    engine.emitResult(transcripts)
  })
  // Click Stop — must finalize transcript into composer WITHOUT auto-sending
  act(() => {
    fireEvent.click(screen.getByRole('button', { name: 'Stop recording' }))
  })
  // User manually clicks Send
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  })
}

describe('Intelligent Voice-to-Text + Adaptive Story Intake Integration', () => {
  const mockGenerator = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    window.localStorage.clear()
    storyIntakePersistence.clearAll()
    useChatStore.getState().resetDemoData()
    MockVoiceEngine.instances = []
    window.SpeechRecognition = MockVoiceEngine

    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
    })

    mockGenerator.mockReset()
    mockGenerator.mockResolvedValue({
      content: 'Story development started from confirmed brief.',
      next_step: 'relationship',
      options: null,
      planner: null,
      suggested_title: null,
    })
    setStoryGenerationRunner(mockGenerator)
  })

  afterEach(() => {
    vi.useRealTimers()
    setStoryGenerationRunner(null)
    delete window.SpeechRecognition
    delete window.webkitSpeechRecognition
  })

  function renderConnectedComposer() {
    let activeConvId: string | undefined
    const utils = render(
      <ChatComposer
        onSend={async (text, attachment, options) => {
          activeConvId = await useChatStore
            .getState()
            .sendMessage(text, attachment, activeConvId ?? null, options)
        }}
      />
    )
    return {
      ...utils,
      getConvId: () => activeConvId,
    }
  }

  it('Scenario A: voice "Tell me a story." asks for title naturally and never generates early', async () => {
    const { getConvId } = renderConnectedComposer()

    await speakAndSubmit([{ transcript: 'Tell me a story.', isFinal: true }])

    const conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.messages[0].inputSource).toBe('voice')
    expect(conv.intakeState?.currentQuestion).toBe('story_title')
    expect(conv.messages[1].content).toMatch(/title/i)
    expect(conv.messages[1].content).not.toMatch(/the user/i)
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('Scenario B: voice "I want a dark fantasy story." extracts Dark fantasy and asks for title', async () => {
    const { getConvId } = renderConnectedComposer()

    await speakAndSubmit([{ transcript: 'I want a dark fantasy story.', isFinal: true }])

    const conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.visualStyle.value).toBe('Dark fantasy')
    expect(conv.intakeState?.currentQuestion).toBe('story_title')
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('Scenario C: voice "Create a story called The Shadow Within." extracts Title and asks visual world', async () => {
    const { getConvId } = renderConnectedComposer()

    await speakAndSubmit([
      { transcript: 'Create a story called The Shadow Within.', isFinal: true },
    ])

    const conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.storyTitle.value).toBe('The Shadow Within')
    expect(conv.intakeState?.currentQuestion).toBe('visual_style')
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('Scenario D: voice "I want a story called The Last Light in anime style." extracts Title + Anime and asks context', async () => {
    const { getConvId } = renderConnectedComposer()

    await speakAndSubmit([
      {
        transcript: 'I want a story called The Last Light in anime style.',
        isFinal: true,
      },
    ])

    const conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.storyTitle.value).toBe('The Last Light')
    expect(conv.intakeState?.visualStyle.value).toBe('Anime')
    expect(conv.intakeState?.currentQuestion).toBe('story_context')
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('Scenario E: voice prompt with all 3 fields shows confirmation summary and waits for explicit confirmation', async () => {
    const { getConvId } = renderConnectedComposer()

    await speakAndSubmit([
      {
        transcript:
          'Create The Last Light, a dark fantasy story about a girl who tries to save her village after the sun disappears.',
        isFinal: true,
      },
    ])

    const conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.storyTitle.value).toBe('The Last Light')
    expect(conv.intakeState?.visualStyle.value).toBe('Dark fantasy')
    expect(conv.intakeState?.storyContext.value).toMatch(/save her village/i)
    expect(conv.intakeState?.status).toBe('awaiting_confirmation')
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('Scenario F: preserves both spoken sentences across a 5-second pause and finalizes trailing interim speech on Stop', async () => {
    const { getConvId } = renderConnectedComposer()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start voice input' }))
    })

    const firstEngine = MockVoiceEngine.instances[0]
    act(() => {
      firstEngine.emitResult([
        { transcript: 'I want to create a story...', isFinal: true },
      ])
    })

    // Natural 5-second pause causes no-speech and browser restart
    act(() => {
      firstEngine.emitError('no-speech')
      firstEngine.emitUnexpectedEnd()
    })
    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    const restartedEngine = MockVoiceEngine.instances[1]
    expect(restartedEngine).toBeDefined()

    // Second sentence arrives as interim right before user clicks Stop
    act(() => {
      restartedEngine.emitResult([
        {
          transcript: '...about a girl who discovers a mysterious shadow.',
          isFinal: false,
        },
      ])
    })

    const textarea = screen.getByLabelText('Message StoryForge') as HTMLTextAreaElement
    expect(textarea.value).toBe(
      'I want to create a story... ...about a girl who discovers a mysterious shadow.'
    )
    // AI must NOT run during interim updates
    expect(getConvId()).toBeUndefined()

    act(() => {
      fireEvent.click(screen.getByRole('button', { name: 'Stop recording' }))
    })
    // Trailing interim text was finalized rather than dropped, and not auto-sent
    expect(textarea.value).toBe(
      'I want to create a story... ...about a girl who discovers a mysterious shadow.'
    )
    expect(getConvId()).toBeUndefined()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    })

    const conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.storyContext.value).toMatch(
      /girl who discovers a mysterious shadow/i
    )
    expect(conv.intakeState?.currentQuestion).toBe('story_title')
    expect(mockGenerator).not.toHaveBeenCalled()
  })

  it('shares the exact same StoryIntakeState when switching seamlessly between typed and spoken turns through confirmation', async () => {
    const { getConvId } = renderConnectedComposer()
    const textarea = screen.getByLabelText('Message StoryForge') as HTMLTextAreaElement

    // Turn 1 (Typed): Title
    fireEvent.change(textarea, {
      target: { value: 'Create a story called The Last Light.' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    })
    let conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.storyTitle.value).toBe('The Last Light')
    expect(conv.intakeState?.currentQuestion).toBe('visual_style')

    // Turn 2 (Voice): Visual style
    await speakAndSubmit([{ transcript: 'Hand-painted animation.', isFinal: true }])
    conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.visualStyle.value).toBe('Hand-painted animation')
    expect(conv.intakeState?.currentQuestion).toBe('story_context')

    // Turn 3 (Typed): Story context
    fireEvent.change(textarea, {
      target: { value: 'A girl tries to save her village after the sun disappears.' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    })
    conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.status).toBe('awaiting_confirmation')
    expect(mockGenerator).not.toHaveBeenCalled()

    // Turn 4 (Voice): Confirm
    await speakAndSubmit([{ transcript: 'Yes, proceed.', isFinal: true }])
    conv = useChatStore.getState().conversations.find((c) => c.id === getConvId())!
    expect(conv.intakeState?.status).toBe('completed')
    expect(mockGenerator).toHaveBeenCalledTimes(1)
  })
})
