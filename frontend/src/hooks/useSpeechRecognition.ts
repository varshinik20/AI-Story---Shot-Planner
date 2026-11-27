import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  SpeechRecognitionConstructor,
  SpeechRecognitionErrorEvent,
  SpeechRecognitionEvent,
  SpeechRecognitionInstance,
} from '@/types/speech-recognition'

export const DEFAULT_SPEECH_LANGUAGE = 'en-IN'
const MAX_UNEXPECTED_RESTARTS = 15
const RESTART_DELAY_MS = 180
const STOP_TIMEOUT_MS = 600

export type SpeechRecordingState =
  | 'idle'
  | 'requesting_permission'
  | 'listening'
  | 'stopping'
  | 'completed'
  | 'error'
  | 'unsupported'

export interface UseSpeechRecognitionOptions {
  language?: string
}

export interface UseSpeechRecognitionReturn {
  isSupported: boolean
  recordingState: SpeechRecordingState
  finalTranscript: string
  interimTranscript: string
  error: string | null
  duration: number
  language: string
  startRecording: () => Promise<void>
  stopRecording: () => void
  resetTranscript: () => void
  clearError: () => void
}

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

export function mergeTranscriptSegments(base: string, addition: string): string {
  const cleanAddition = addition.trim()
  if (!cleanAddition) return base
  const cleanBase = base.trimEnd()
  if (!cleanBase) return cleanAddition
  return `${cleanBase} ${cleanAddition}`
}

function mapSpeechErrorMessage(code: string): string {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone permission denied. Please allow microphone access in your browser settings.'
    case 'audio-capture':
      return 'No microphone was found. Please connect a microphone and try again.'
    case 'network':
      return 'Network error during speech recognition. Check your internet connection and try again.'
    case 'language-not-supported':
      return 'The selected speech recognition language is not supported by this browser.'
    default:
      return 'Speech recognition service encountered an error. You can continue typing your story.'
  }
}

export function useSpeechRecognition(
  options: UseSpeechRecognitionOptions = {}
): UseSpeechRecognitionReturn {
  const language = options.language ?? DEFAULT_SPEECH_LANGUAGE
  const [isSupported, setIsSupported] = useState<boolean>(() =>
    Boolean(getSpeechRecognitionConstructor())
  )
  const [recordingState, setRecordingState] = useState<SpeechRecordingState>('idle')
  const [finalTranscript, setFinalTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [duration, setDuration] = useState(0)

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)
  const recordingStateRef = useRef<SpeechRecordingState>('idle')
  const intentionalStopRef = useRef(false)
  const committedFinalRef = useRef('')
  const currentInstanceFinalRef = useRef('')
  const restartCountRef = useRef(0)
  const restartTimerRef = useRef<number | null>(null)
  const stopTimerRef = useRef<number | null>(null)
  const durationTimerRef = useRef<number | null>(null)
  const isMountedRef = useRef(true)

  const updateState = useCallback((next: SpeechRecordingState) => {
    recordingStateRef.current = next
    if (isMountedRef.current) {
      setRecordingState(next)
    }
  }, [])

  const clearTimers = useCallback(() => {
    if (restartTimerRef.current !== null) {
      window.clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
    if (stopTimerRef.current !== null) {
      window.clearTimeout(stopTimerRef.current)
      stopTimerRef.current = null
    }
    if (durationTimerRef.current !== null) {
      window.clearInterval(durationTimerRef.current)
      durationTimerRef.current = null
    }
  }, [])

  const cleanupRecognitionInstance = useCallback(() => {
    const rec = recognitionRef.current
    if (!rec) return
    rec.onstart = null
    rec.onresult = null
    rec.onerror = null
    rec.onend = null
    try {
      rec.abort()
    } catch {
      // Ignore abort errors on already-stopped instances
    }
    recognitionRef.current = null
  }, [])

  // Keep duration ticking only while listening
  useEffect(() => {
    if (recordingState === 'listening') {
      durationTimerRef.current = window.setInterval(() => {
        if (isMountedRef.current) {
          setDuration((prev) => prev + 1)
        }
      }, 1000)
      return () => {
        if (durationTimerRef.current !== null) {
          window.clearInterval(durationTimerRef.current)
          durationTimerRef.current = null
        }
      }
    }
    return undefined
  }, [recordingState])

  // Re-evaluate support on mount (SSR-safe) and clean up on unmount
  useEffect(() => {
    isMountedRef.current = true
    setIsSupported(Boolean(getSpeechRecognitionConstructor()))

    return () => {
      isMountedRef.current = false
      intentionalStopRef.current = true
      clearTimers()
      cleanupRecognitionInstance()
    }
  }, [clearTimers, cleanupRecognitionInstance])

  const finalizeSession = useCallback(() => {
    clearTimers()
    const merged = mergeTranscriptSegments(
      committedFinalRef.current,
      currentInstanceFinalRef.current
    )
    committedFinalRef.current = merged
    currentInstanceFinalRef.current = ''
    cleanupRecognitionInstance()

    if (isMountedRef.current) {
      setFinalTranscript(merged)
      setInterimTranscript('')
    }
    updateState('completed')
  }, [cleanupRecognitionInstance, clearTimers, updateState])

  const spawnRecognitionSession = useCallback(() => {
    const SpeechCtor = getSpeechRecognitionConstructor()
    if (!SpeechCtor) {
      setIsSupported(false)
      setError('Voice input is not supported in this browser. Please use Chrome or Edge, or type your story below.')
      updateState('unsupported')
      return
    }

    cleanupRecognitionInstance()

    const recognition = new SpeechCtor()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = language
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      if (!isMountedRef.current) return
      if (intentionalStopRef.current) {
        try {
          recognition.stop()
        } catch {
          // Ignore
        }
        return
      }
      updateState('listening')
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      if (!isMountedRef.current) return

      // Successful speech resets unexpected-restart counter
      restartCountRef.current = 0

      let instanceFinal = ''
      let instanceInterim = ''

      for (let i = 0; i < event.results.length; i += 1) {
        const result = event.results[i]
        const transcriptPiece = result?.[0]?.transcript ?? ''
        if (!transcriptPiece) continue

        if (result.isFinal) {
          instanceFinal = mergeTranscriptSegments(instanceFinal, transcriptPiece)
        } else {
          instanceInterim = mergeTranscriptSegments(instanceInterim, transcriptPiece)
        }
      }

      currentInstanceFinalRef.current = instanceFinal
      const combinedFinal = mergeTranscriptSegments(committedFinalRef.current, instanceFinal)
      setFinalTranscript(combinedFinal)
      setInterimTranscript(instanceInterim)
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (!isMountedRef.current) return

      const code = event.error

      // Natural pauses often trigger 'no-speech'; keep continuous listening alive
      if (code === 'no-speech') {
        return
      }

      if (code === 'aborted' && intentionalStopRef.current) {
        return
      }

      intentionalStopRef.current = true
      clearTimers()
      const merged = mergeTranscriptSegments(
        committedFinalRef.current,
        currentInstanceFinalRef.current
      )
      committedFinalRef.current = merged
      currentInstanceFinalRef.current = ''
      cleanupRecognitionInstance()

      setFinalTranscript(merged)
      setInterimTranscript('')
      setError(mapSpeechErrorMessage(code))
      updateState('error')
    }

    recognition.onend = () => {
      if (!isMountedRef.current) return

      // Commit any final results from this instance before deciding next step
      const merged = mergeTranscriptSegments(
        committedFinalRef.current,
        currentInstanceFinalRef.current
      )
      committedFinalRef.current = merged
      currentInstanceFinalRef.current = ''
      setFinalTranscript(merged)

      if (intentionalStopRef.current || recordingStateRef.current === 'stopping') {
        finalizeSession()
        return
      }

      if (recordingStateRef.current === 'error' || recordingStateRef.current === 'unsupported') {
        return
      }

      // Unexpected termination during active listening: restart seamlessly up to safety cap
      if (restartCountRef.current >= MAX_UNEXPECTED_RESTARTS) {
        intentionalStopRef.current = true
        setInterimTranscript('')
        setError('Voice recognition ended unexpectedly. Your spoken text has been preserved.')
        updateState('error')
        return
      }

      restartCountRef.current += 1
      restartTimerRef.current = window.setTimeout(() => {
        if (!isMountedRef.current || intentionalStopRef.current) return
        spawnRecognitionSession()
      }, RESTART_DELAY_MS)
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {
      intentionalStopRef.current = true
      cleanupRecognitionInstance()
      setError('Could not start speech recognition. Please try again.')
      updateState('error')
    }
  }, [cleanupRecognitionInstance, clearTimers, finalizeSession, language, updateState])

  const startRecording = useCallback(async () => {
    // Prevent multiple simultaneous recognition sessions
    if (
      recordingStateRef.current === 'requesting_permission' ||
      recordingStateRef.current === 'listening' ||
      recordingStateRef.current === 'stopping'
    ) {
      return
    }

    const SpeechCtor = getSpeechRecognitionConstructor()
    if (!SpeechCtor) {
      setIsSupported(false)
      setError(
        'Voice input is not supported in this browser. Please use Google Chrome or Microsoft Edge, or type your story below.'
      )
      updateState('unsupported')
      return
    }

    setIsSupported(true)
    setError(null)
    setFinalTranscript('')
    setInterimTranscript('')
    setDuration(0)
    committedFinalRef.current = ''
    currentInstanceFinalRef.current = ''
    restartCountRef.current = 0
    intentionalStopRef.current = false
    updateState('requesting_permission')

    // Request microphone permission explicitly only upon user click
    if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        // Immediately release temporary permission-check tracks; Web Speech manages its own mic
        stream.getTracks().forEach((track) => track.stop())
      } catch (err) {
        if (!isMountedRef.current) return
        const name = err instanceof Error ? err.name : ''
        if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
          setError(mapSpeechErrorMessage('audio-capture'))
        } else {
          setError(mapSpeechErrorMessage('not-allowed'))
        }
        updateState('error')
        return
      }
    }

    if (!isMountedRef.current || intentionalStopRef.current) return
    spawnRecognitionSession()
  }, [spawnRecognitionSession, updateState])

  const stopRecording = useCallback(() => {
    if (
      recordingStateRef.current !== 'listening' &&
      recordingStateRef.current !== 'requesting_permission'
    ) {
      return
    }

    intentionalStopRef.current = true
    if (restartTimerRef.current !== null) {
      window.clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }

    updateState('stopping')

    const rec = recognitionRef.current
    if (rec) {
      try {
        rec.stop()
      } catch {
        finalizeSession()
        return
      }

      // Safety fallback if browser does not fire onend promptly
      stopTimerRef.current = window.setTimeout(() => {
        if (recordingStateRef.current === 'stopping') {
          finalizeSession()
        }
      }, STOP_TIMEOUT_MS)
    } else {
      finalizeSession()
    }
  }, [finalizeSession, updateState])

  const resetTranscript = useCallback(() => {
    committedFinalRef.current = ''
    currentInstanceFinalRef.current = ''
    if (isMountedRef.current) {
      setFinalTranscript('')
      setInterimTranscript('')
      setDuration(0)
      if (recordingStateRef.current === 'completed') {
        updateState('idle')
      }
    }
  }, [updateState])

  const clearError = useCallback(() => {
    setError(null)
    if (recordingStateRef.current === 'error' || recordingStateRef.current === 'unsupported') {
      updateState('idle')
    }
  }, [updateState])

  return {
    isSupported,
    recordingState,
    finalTranscript,
    interimTranscript,
    error,
    duration,
    language,
    startRecording,
    stopRecording,
    resetTranscript,
    clearError,
  }
}
