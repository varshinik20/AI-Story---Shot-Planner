import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition'
import type {
  SpeechRecognitionErrorEvent,
  SpeechRecognitionEvent,
  SpeechRecognitionInstance,
  SpeechRecognitionResult,
  SpeechRecognitionResultList,
} from '@/types/speech-recognition'

class MockSpeechRecognition implements SpeechRecognitionInstance {
  static instances: MockSpeechRecognition[] = []

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

  started = false
  stopped = false
  aborted = false

  constructor() {
    MockSpeechRecognition.instances.push(this)
  }

  addEventListener(): void {}
  removeEventListener(): void {}
  dispatchEvent(): boolean {
    return true
  }

  start(): void {
    this.started = true
    this.onstart?.call(this, new Event('start'))
  }

  stop(): void {
    this.stopped = true
    this.onend?.call(this, new Event('end'))
  }

  abort(): void {
    this.aborted = true
  }

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

    const event = {
      resultIndex: 0,
      results,
    } as SpeechRecognitionEvent

    this.onresult?.call(this, event)
  }

  emitError(code: string): void {
    const event = {
      error: code,
      message: code,
    } as SpeechRecognitionErrorEvent
    this.onerror?.call(this, event)
  }

  emitUnexpectedEnd(): void {
    this.onend?.call(this, new Event('end'))
  }
}

describe('useSpeechRecognition', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    MockSpeechRecognition.instances = []
    window.SpeechRecognition = MockSpeechRecognition
    window.webkitSpeechRecognition = undefined

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
    vi.useRealTimers()
    delete window.SpeechRecognition
    delete window.webkitSpeechRecognition
  })

  it('detects browser support via SpeechRecognition and webkitSpeechRecognition fallback', () => {
    const { result } = renderHook(() => useSpeechRecognition())
    expect(result.current.isSupported).toBe(true)
    expect(result.current.language).toBe('en-IN')

    delete window.SpeechRecognition
    window.webkitSpeechRecognition = MockSpeechRecognition

    const { result: fallbackResult } = renderHook(() =>
      useSpeechRecognition({ language: 'en-US' })
    )
    expect(fallbackResult.current.isSupported).toBe(true)
    expect(fallbackResult.current.language).toBe('en-US')
  })

  it('handles unsupported browsers safely without crashing', async () => {
    delete window.SpeechRecognition
    delete window.webkitSpeechRecognition

    const { result } = renderHook(() => useSpeechRecognition())
    expect(result.current.isSupported).toBe(false)

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.recordingState).toBe('unsupported')
    expect(result.current.error).toMatch(/not supported/i)
  })

  it('starts continuous recognition, handles interim & final transcripts without duplicates, and stops intentionally', async () => {
    const { result } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.recordingState).toBe('listening')
    const instance = MockSpeechRecognition.instances[0]
    expect(instance.continuous).toBe(true)
    expect(instance.interimResults).toBe(true)
    expect(instance.lang).toBe('en-IN')
    expect(instance.maxAlternatives).toBe(1)

    // Repeated interim updates should not duplicate words
    act(() => {
      instance.emitResult([{ transcript: 'I want to', isFinal: false }])
    })
    expect(result.current.interimTranscript).toBe('I want to')
    expect(result.current.finalTranscript).toBe('')

    act(() => {
      instance.emitResult([
        { transcript: 'I want to create a story about a young girl.', isFinal: true },
        { transcript: 'She discovers', isFinal: false },
      ])
    })
    expect(result.current.finalTranscript).toBe(
      'I want to create a story about a young girl.'
    )
    expect(result.current.interimTranscript).toBe('She discovers')

    // Intentional stop while interim results exist should finalize and clear interim
    act(() => {
      result.current.stopRecording()
    })

    expect(result.current.recordingState).toBe('completed')
    expect(result.current.interimTranscript).toBe('')
    expect(result.current.finalTranscript).toBe(
      'I want to create a story about a young girl.'
    )
    expect(MockSpeechRecognition.instances).toHaveLength(1)
  })

  it('automatically restarts on unexpected end during pauses and accumulates transcripts without losing prior words', async () => {
    const { result } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
    })

    const first = MockSpeechRecognition.instances[0]
    act(() => {
      first.emitResult([
        { transcript: 'I want to create a story about a young girl.', isFinal: true },
      ])
    })

    // Simulate browser emitting no-speech + unexpected end after a pause
    act(() => {
      first.emitError('no-speech')
      first.emitUnexpectedEnd()
    })

    expect(result.current.finalTranscript).toBe(
      'I want to create a story about a young girl.'
    )

    await act(async () => {
      vi.advanceTimersByTime(200)
    })

    expect(MockSpeechRecognition.instances).toHaveLength(2)
    expect(result.current.recordingState).toBe('listening')

    const second = MockSpeechRecognition.instances[1]
    act(() => {
      second.emitResult([
        {
          transcript: 'She discovers a mysterious shadow inside her bedroom.',
          isFinal: true,
        },
      ])
    })

    expect(result.current.finalTranscript).toBe(
      'I want to create a story about a young girl. She discovers a mysterious shadow inside her bedroom.'
    )
  })

  it('prevents multiple simultaneous recording sessions', async () => {
    const { result } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
      await result.current.startRecording()
    })

    expect(MockSpeechRecognition.instances).toHaveLength(1)
  })

  it('handles microphone permission denial cleanly', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi
          .fn()
          .mockRejectedValue(Object.assign(new Error('Denied'), { name: 'NotAllowedError' })),
      },
    })

    const { result } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.recordingState).toBe('error')
    expect(result.current.error).toMatch(/permission denied/i)
    expect(MockSpeechRecognition.instances).toHaveLength(0)
  })

  it('handles network error from SpeechRecognition and preserves finalized text', async () => {
    const { result } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
    })

    const instance = MockSpeechRecognition.instances[0]
    act(() => {
      instance.emitResult([{ transcript: 'Partial story.', isFinal: true }])
      instance.emitError('network')
    })

    expect(result.current.recordingState).toBe('error')
    expect(result.current.error).toMatch(/network error/i)
    expect(result.current.finalTranscript).toBe('Partial story.')
  })

  it('handles empty recording session without adding spurious text or errors', async () => {
    const { result } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
    })
    act(() => {
      result.current.stopRecording()
    })

    expect(result.current.recordingState).toBe('completed')
    expect(result.current.finalTranscript).toBe('')
    expect(result.current.interimTranscript).toBe('')
    expect(result.current.error).toBeNull()
  })

  it('cleans up active recognition instance on unmount', async () => {
    const { result, unmount } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
    })

    const instance = MockSpeechRecognition.instances[0]
    unmount()

    expect(instance.aborted).toBe(true)
  })

  it('preserves intentional repeated words across natural pauses and exposes unique sessionId', async () => {
    const { result } = renderHook(() => useSpeechRecognition())

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.language).toBe('en-IN')
    expect(result.current.sessionId).toMatch(/^rec-/)

    const instance = MockSpeechRecognition.instances[0]
    act(() => {
      instance.emitResult([
        { transcript: 'Wolf!', isFinal: true },
        { transcript: 'Wolf!', isFinal: true },
      ])
    })

    expect(result.current.finalTranscript).toBe('Wolf! Wolf!')
  })
})
