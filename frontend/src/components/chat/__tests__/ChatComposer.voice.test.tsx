import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatComposer } from '@/components/chat/ChatComposer'
import type {
  SpeechRecognitionErrorEvent,
  SpeechRecognitionEvent,
  SpeechRecognitionInstance,
  SpeechRecognitionResult,
  SpeechRecognitionResultList,
} from '@/types/speech-recognition'

class MockComposerRecognition implements SpeechRecognitionInstance {
  static latest: MockComposerRecognition | null = null

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

  constructor() {
    MockComposerRecognition.latest = this
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
    this.onend?.call(this, new Event('end'))
  }

  abort(): void {}

  emitResult(items: Array<{ transcript: string; isFinal: boolean }>): void {
    const resultObjs: SpeechRecognitionResult[] = items.map((item) => {
      const alt = { transcript: item.transcript, confidence: 0.95 }
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
}

describe('ChatComposer voice integration', () => {
  beforeEach(() => {
    MockComposerRecognition.latest = null
    window.SpeechRecognition = MockComposerRecognition
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
    })
  })

  afterEach(() => {
    delete window.SpeechRecognition
    delete window.webkitSpeechRecognition
  })

  it('preserves existing typed text, displays interim/final text, never auto-submits, and allows editing before manual send', async () => {
    const onSend = vi.fn()
    render(<ChatComposer onSend={onSend} conversationId="conv_1" />)

    const textarea = screen.getByLabelText('Message StoryForge') as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: 'Create a cinematic story about trust.' } })

    const startBtn = screen.getByRole('button', { name: 'Start voice input' })
    await act(async () => {
      fireEvent.click(startBtn)
    })

    expect(screen.getByText('Listening...')).toBeInTheDocument()
    const stopBtn = screen.getByRole('button', { name: 'Stop recording' })
    expect(stopBtn).toBeInTheDocument()

    // Interim transcript appears alongside preserved existing text
    act(() => {
      MockComposerRecognition.latest?.emitResult([
        { transcript: 'The story should have', isFinal: false },
      ])
    })
    expect(textarea.value).toBe(
      'Create a cinematic story about trust. The story should have'
    )

    // Final transcript replaces interim cleanly
    act(() => {
      MockComposerRecognition.latest?.emitResult([
        { transcript: 'The story should have an emotional ending.', isFinal: true },
      ])
    })
    expect(textarea.value).toBe(
      'Create a cinematic story about trust. The story should have an emotional ending.'
    )

    // Stop recording: must NOT auto-submit
    act(() => {
      fireEvent.click(stopBtn)
    })
    expect(onSend).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Start voice input' })).toBeInTheDocument()

    // User can edit recognized text and manually send
    fireEvent.change(textarea, {
      target: { value: `${textarea.value} Set at twilight.` },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(onSend).toHaveBeenCalledTimes(1)
    expect(onSend).toHaveBeenCalledWith(
      'Create a cinematic story about trust. The story should have an emotional ending. Set at twilight.',
      undefined
    )
    expect(textarea.value).toBe('')
  })

  it('keeps typed submission working when Web Speech API is unsupported', async () => {
    delete window.SpeechRecognition
    delete window.webkitSpeechRecognition

    const onSend = vi.fn()
    render(<ChatComposer onSend={onSend} conversationId="conv_1" />)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start voice input' }))
    })
    expect(screen.getByRole('alert')).toHaveTextContent(/not supported/i)

    const textarea = screen.getByLabelText('Message StoryForge')
    fireEvent.change(textarea, { target: { value: 'A quiet lighthouse story.' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })

    expect(onSend).toHaveBeenCalledWith('A quiet lighthouse story.', undefined)
  })

  it('stops active recording when navigating to another conversation', async () => {
    const onSend = vi.fn()
    const { rerender } = render(<ChatComposer onSend={onSend} conversationId="conv_1" />)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Start voice input' }))
    })
    expect(screen.getByRole('button', { name: 'Stop recording' })).toBeInTheDocument()

    rerender(<ChatComposer onSend={onSend} conversationId="conv_2" />)
    expect(screen.getByRole('button', { name: 'Start voice input' })).toBeInTheDocument()
  })
})
