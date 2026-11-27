import { Loader2, Mic, Square } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SpeechRecordingState } from '@/hooks/useSpeechRecognition'

interface VoiceInputButtonProps {
  recordingState: SpeechRecordingState
  isSupported: boolean
  duration: number
  disabled?: boolean
  onStart: () => void
  onStop: () => void
}

function formatRecordingDuration(totalSeconds: number): string {
  const mins = Math.floor(totalSeconds / 60)
  const secs = totalSeconds % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

export function VoiceInputButton({
  recordingState,
  isSupported,
  duration,
  disabled = false,
  onStart,
  onStop,
}: VoiceInputButtonProps) {
  const isListening = recordingState === 'listening'
  const isStopping = recordingState === 'stopping'
  const isRequesting = recordingState === 'requesting_permission'
  const isActive = isListening || isStopping

  if (isActive) {
    return (
      <div className="flex shrink-0 items-center gap-2">
        <div
          className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-2 py-1 text-[11.5px] font-medium text-red-700 sm:gap-2 sm:px-2.5"
          role="status"
          aria-live="polite"
        >
          <span className="h-2 w-2 rounded-full bg-red-600 animate-pulse" />
          <span className="flex items-end gap-0.5 h-3" aria-hidden="true">
            <span className="w-0.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span className="w-0.5 h-3 rounded-full bg-red-600 animate-pulse" />
            <span className="w-0.5 h-2 rounded-full bg-red-500 animate-pulse" />
          </span>
          <span className="hidden sm:inline">
            {isStopping ? 'Finalizing...' : 'Listening...'}
          </span>
          <span className="font-mono text-[11px] tabular-nums text-red-600">
            {formatRecordingDuration(duration)}
          </span>
        </div>

        <button
          type="button"
          onClick={onStop}
          disabled={isStopping}
          title="Stop recording"
          aria-label="Stop recording"
          className={cn(
            'relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-red-300 bg-red-600 text-white transition-colors hover:bg-red-700',
            isStopping && 'opacity-70 cursor-wait'
          )}
        >
          <Square className="h-3.5 w-3.5 fill-current" />
        </button>
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={onStart}
      disabled={disabled || isRequesting}
      title={
        isRequesting
          ? 'Requesting microphone...'
          : isSupported
          ? 'Start voice input'
          : 'Voice input unavailable in this browser'
      }
      aria-label={
        isRequesting
          ? 'Requesting microphone permission'
          : 'Start voice input'
      }
      className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors',
        isRequesting
          ? 'bg-[#F1F1F1] text-[#10A37F]'
          : !isSupported
          ? 'text-[#9CA3AF] hover:bg-[#EAEAEA] hover:text-[#6B7280]'
          : 'text-[#6B7280] hover:bg-[#EAEAEA] hover:text-[#212121]',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      {isRequesting ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Mic className="h-4 w-4" />
      )}
    </button>
  )
}
