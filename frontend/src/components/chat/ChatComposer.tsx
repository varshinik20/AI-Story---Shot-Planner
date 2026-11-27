import { useEffect, useRef, useState } from 'react'
import { ArrowUp, FileText, FileType, Paperclip, X } from 'lucide-react'
import { cn, generateId } from '@/lib/utils'
import type { UploadedAttachment } from '@/types/chat'
import { useChatStore } from '@/store/chatStore'
import {
  mergeTranscriptSegments,
  useSpeechRecognition,
} from '@/hooks/useSpeechRecognition'
import { VoiceInputButton } from './VoiceInputButton'

interface ChatComposerProps {
  onSend: (
    text: string,
    attachment?: UploadedAttachment,
    options?: { inputSource?: 'text' | 'voice' }
  ) => void
  disabled?: boolean
  conversationId?: string
  speechLanguage?: string
}

const ACCEPTED_EXTENSIONS: Record<string, UploadedAttachment['type']> = {
  pdf: 'pdf',
  txt: 'txt',
  docx: 'docx',
}

export function ChatComposer({
  onSend,
  disabled = false,
  conversationId,
  speechLanguage,
}: ChatComposerProps) {
  const { focusComposerSignal, composerPrefill, clearComposerPrefill } = useChatStore()

  const [text, setText] = useState('')
  const [attachment, setAttachment] = useState<UploadedAttachment | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [attachMenuOpen, setAttachMenuOpen] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const baseTextBeforeRecordingRef = useRef('')
  const prevRecordingStateRef = useRef<string>('idle')
  const usedVoiceRef = useRef(false)
  const ignoreNextCompletionCommitRef = useRef(false)

  const {
    isSupported: isSpeechSupported,
    recordingState,
    finalTranscript,
    completeTranscript,
    error: speechError,
    duration: recordingDuration,
    startRecording,
    stopRecording,
    resetTranscript,
    clearError: clearSpeechError,
  } = useSpeechRecognition({ language: speechLanguage })

  const isListeningOrStopping =
    recordingState === 'listening' || recordingState === 'stopping'

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const nextHeight = Math.min(el.scrollHeight, 180)
    el.style.height = `${nextHeight}px`
  }, [text])

  // Focus composer when "Let me explain in my own words" or "Custom direction" is clicked
  useEffect(() => {
    if (focusComposerSignal > 0) {
      if (composerPrefill) {
        setText(composerPrefill)
        clearComposerPrefill()
      }
      textareaRef.current?.focus()
    }
  }, [focusComposerSignal, composerPrefill, clearComposerPrefill])

  // Close attach popover on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setAttachMenuOpen(false)
      }
    }
    if (attachMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [attachMenuOpen])

  // Stop active voice session if the user switches conversations without leaking partial transcripts
  const prevConversationIdRef = useRef<string | undefined>(conversationId)
  useEffect(() => {
    const switchedBetweenExisting =
      prevConversationIdRef.current !== undefined &&
      prevConversationIdRef.current !== conversationId
    prevConversationIdRef.current = conversationId

    if (
      switchedBetweenExisting &&
      (recordingState === 'listening' || recordingState === 'requesting_permission')
    ) {
      ignoreNextCompletionCommitRef.current = true
      stopRecording()
      setText('')
      baseTextBeforeRecordingRef.current = ''
      usedVoiceRef.current = false
      resetTranscript()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId])

  // Synchronize live speech transcription with preserved composer text without auto-sending
  useEffect(() => {
    const prevState = prevRecordingStateRef.current
    prevRecordingStateRef.current = recordingState

    if (recordingState === 'listening' || recordingState === 'stopping') {
      if (completeTranscript) {
        usedVoiceRef.current = true
      }
      const nextText = mergeTranscriptSegments(
        baseTextBeforeRecordingRef.current,
        completeTranscript
      )
      setText(nextText)
      return
    }

    if (
      (recordingState === 'completed' || recordingState === 'error') &&
      (prevState === 'listening' ||
        prevState === 'stopping' ||
        prevState === 'requesting_permission')
    ) {
      if (ignoreNextCompletionCommitRef.current) {
        ignoreNextCompletionCommitRef.current = false
        resetTranscript()
        return
      }
      if (finalTranscript) {
        usedVoiceRef.current = true
      }
      const committed = mergeTranscriptSegments(
        baseTextBeforeRecordingRef.current,
        finalTranscript
      )
      setText(committed)
      baseTextBeforeRecordingRef.current = committed
      resetTranscript()
      textareaRef.current?.focus()
    }
  }, [recordingState, finalTranscript, completeTranscript, resetTranscript])

  const canSend = (text.trim().length > 0 || attachment !== null) && !disabled

  const handleSubmit = () => {
    if (!canSend) return
    const finalMessageText = text
    const inputSource: 'text' | 'voice' = usedVoiceRef.current ? 'voice' : 'text'
    if (isListeningOrStopping) {
      ignoreNextCompletionCommitRef.current = true
      stopRecording()
    }
    onSend(finalMessageText, attachment ?? undefined, { inputSource })
    setText('')
    baseTextBeforeRecordingRef.current = ''
    usedVoiceRef.current = false
    setAttachment(null)
    setFileError(null)
    resetTranscript()
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleStartVoice = () => {
    ignoreNextCompletionCommitRef.current = false
    baseTextBeforeRecordingRef.current = text
    clearSpeechError()
    void startRecording()
  }

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const nextValue = e.target.value
    setText(nextValue)
    if (!nextValue.trim()) {
      usedVoiceRef.current = false
    }
    if (!isListeningOrStopping) {
      baseTextBeforeRecordingRef.current = nextValue
    }
  }

  const triggerFilePicker = (acceptFilter: string) => {
    setAttachMenuOpen(false)
    if (!fileInputRef.current) return
    fileInputRef.current.accept = acceptFilter
    fileInputRef.current.value = ''
    fileInputRef.current.click()
  }

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    const mappedType = ACCEPTED_EXTENSIONS[ext]

    if (!mappedType) {
      setFileError('Unsupported file type. Please upload a PDF, TXT, or DOCX document.')
      return
    }

    if (file.size > 15 * 1024 * 1024) {
      setFileError('File exceeds 15 MB limit. Please select a smaller story document.')
      return
    }

    let previewText: string | undefined
    if (mappedType === 'txt') {
      try {
        const raw = await file.text()
        previewText = raw.slice(0, 220).trim()
      } catch {
        previewText = undefined
      }
    }

    setFileError(null)
    setAttachment({
      id: generateId('file'),
      name: file.name,
      size: file.size,
      type: mappedType,
      previewText,
    })
  }

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const activeError = fileError || speechError

  return (
    <div className="w-full px-3 pb-4 pt-2 sm:px-6">
      <div className="mx-auto w-full max-w-3xl">
        {/* Inline validation / speech recognition error */}
        {activeError && (
          <div
            role="alert"
            className="mb-2 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
          >
            <span>{activeError}</span>
            <button
              type="button"
              onClick={() => {
                if (fileError) setFileError(null)
                if (speechError) clearSpeechError()
              }}
              className="rounded p-0.5 hover:bg-red-100"
              aria-label="Dismiss error"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Rounded ChatGPT-style Composer */}
        <div
          className={cn(
            'relative rounded-3xl border bg-[#F9F9F9] px-3 py-2.5 transition-colors focus-within:bg-white',
            isListeningOrStopping
              ? 'border-red-300 bg-white'
              : 'border-[#E5E7EB] focus-within:border-[#D1D5DB]'
          )}
        >
          {/* Attachment Chip Preview */}
          {attachment && (
            <div className="mb-2 flex items-center">
              <div className="inline-flex items-center gap-2 rounded-xl border border-[#E5E7EB] bg-white px-3 py-1.5 text-xs text-[#212121]">
                <FileText className="h-3.5 w-3.5 text-[#10A37F]" />
                <span className="max-w-[200px] truncate font-medium">{attachment.name}</span>
                <span className="uppercase text-[10px] text-[#6B7280]">
                  {attachment.type} • {formatBytes(attachment.size)}
                </span>
                <button
                  type="button"
                  onClick={() => setAttachment(null)}
                  aria-label="Remove attachment"
                  className="ml-0.5 rounded-full p-0.5 text-[#6B7280] hover:bg-[#F1F1F1] hover:text-[#212121]"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileSelected}
          />

          <div className="flex items-end gap-2">
            {/* Attachment Popover Button */}
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setAttachMenuOpen((prev) => !prev)}
                aria-label="Attach story document"
                title="Upload PDF, TXT, or DOCX"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[#6B7280] transition-colors hover:bg-[#EAEAEA] hover:text-[#212121]"
              >
                <Paperclip className="h-4 w-4" />
              </button>

              {attachMenuOpen && (
                <div className="absolute bottom-11 left-0 z-30 w-48 rounded-xl border border-[#E5E7EB] bg-white p-1.5 shadow-md">
                  <div className="px-2.5 py-1 text-[11px] font-medium text-[#6B7280]">
                    Attach story document
                  </div>
                  <button
                    type="button"
                    onClick={() => triggerFilePicker('.pdf,application/pdf')}
                    className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-[#212121] hover:bg-[#F1F1F1]"
                  >
                    <FileText className="h-3.5 w-3.5 text-red-500" />
                    <span>Upload PDF</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => triggerFilePicker('.txt,text/plain')}
                    className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-[#212121] hover:bg-[#F1F1F1]"
                  >
                    <FileType className="h-3.5 w-3.5 text-[#10A37F]" />
                    <span>Upload TXT</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      triggerFilePicker(
                        '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                      )
                    }
                    className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-[#212121] hover:bg-[#F1F1F1]"
                  >
                    <FileText className="h-3.5 w-3.5 text-blue-600" />
                    <span>Upload DOCX</span>
                  </button>
                </div>
              )}
            </div>

            {/* Auto-resizing Multiline Textarea */}
            <textarea
              ref={textareaRef}
              rows={1}
              value={text}
              onChange={handleTextChange}
              onKeyDown={handleKeyDown}
              placeholder="Describe your story or upload a document..."
              aria-label="Message StoryForge"
              className="max-h-[180px] min-h-[24px] flex-1 resize-none bg-transparent py-1.5 text-[14.5px] leading-relaxed text-[#212121] placeholder:text-[#6B7280] focus:outline-none"
            />

            {/* Voice Recording Control */}
            <VoiceInputButton
              recordingState={recordingState}
              isSupported={isSpeechSupported}
              duration={recordingDuration}
              disabled={disabled}
              onStart={handleStartVoice}
              onStop={stopRecording}
            />

            {/* Send Button */}
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSend}
              aria-label="Send message"
              title="Send message"
              className={cn(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors',
                canSend
                  ? 'bg-[#212121] text-white hover:bg-[#373737]'
                  : 'bg-[#E5E7EB] text-[#9CA3AF] cursor-not-allowed'
              )}
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </div>

        <p className="mt-2 text-center text-[11px] text-[#6B7280]">
          StoryForge runs in local demo mode. Press <kbd className="font-sans font-medium">Enter</kbd> to send, <kbd className="font-sans font-medium">Shift + Enter</kbd> for a new line.
        </p>
      </div>
    </div>
  )
}
