import { useRef, useState } from 'react'
import { Check, Copy, FileText, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/types/chat'
import { useChatStore } from '@/store/chatStore'
import { useProjectStore } from '@/store/projectStore'
import { StoryForgeLogo } from '@/components/common/StoryForgeLogo'
import { StorySuggestion } from './StorySuggestion'
import { ProjectOverview } from '@/components/planner/ProjectOverview'
import { CharacterSection } from '@/components/planner/CharacterSection'
import { LocationSection } from '@/components/planner/LocationSection'
import { SceneAccordion } from '@/components/planner/SceneAccordion'
import { ApprovalPanel } from '@/components/planner/ApprovalPanel'

interface MessageBubbleProps {
  conversationId: string
  message: ChatMessage
}

export function MessageBubble({ conversationId, message }: MessageBubbleProps) {
  const {
    selectOption,
    updateSuggestionStatus,
    regenerateAssistantMessage,
    triggerComposerFocus,
  } = useChatStore()
  const planner = useProjectStore((s) =>
    message.plannerId ? s.planners[message.plannerId] : undefined
  )

  const [copied, setCopied] = useState(false)
  const [editNotice, setEditNotice] = useState(false)
  const scenesTopRef = useRef<HTMLDivElement>(null)

  const isUser = message.role === 'user'

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  const handleRequestEdit = () => {
    setEditNotice(true)
    scenesTopRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setTimeout(() => setEditNotice(false), 3500)
  }

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18 }}
        className="flex justify-end py-2"
      >
        <div className="max-w-[85%] space-y-2 sm:max-w-[75%]">
          {message.attachment && (
            <div className="ml-auto inline-flex items-center gap-2 rounded-xl border border-[#E5E7EB] bg-[#F9F9F9] px-3 py-1.5 text-xs text-[#212121]">
              <FileText className="h-3.5 w-3.5 text-[#10A37F]" />
              <span className="font-medium">{message.attachment.name}</span>
              <span className="uppercase text-[10px] text-[#6B7280]">
                {message.attachment.type}
              </span>
            </div>
          )}
          <div className="rounded-3xl bg-[#F4F4F4] px-4 py-2.5 text-[14.5px] leading-relaxed text-[#212121]">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="group flex items-start gap-3.5 py-3"
    >
      <StoryForgeLogo className="mt-0.5 h-7 w-7 shrink-0" />

      <div className="min-w-0 flex-1 space-y-4">
        {/* Assistant Markdown Prose */}
        <div className="sf-markdown text-[14.5px] text-[#212121]">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>

        {/* Inline Story Improvement Suggestions */}
        {message.suggestions && message.suggestions.length > 0 && (
          <div className="space-y-3">
            {message.suggestions.map((sug) => (
              <StorySuggestion
                key={sug.id}
                suggestion={sug}
                onDecision={(sugId, status) =>
                  updateSuggestionStatus(conversationId, message.id, sugId, status)
                }
              />
            ))}
          </div>
        )}

        {/* Clickable Option Chips (Relationship & Creative Intent Interview) */}
        {message.options && message.options.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-0.5">
            {message.options.map((opt) => {
              const isSelected = message.selectedOptionId === opt.id
              const hasSelection = Boolean(message.selectedOptionId)

              return (
                <button
                  key={opt.id}
                  type="button"
                  disabled={hasSelection && opt.action !== 'focus_input'}
                  onClick={() => {
                    if (opt.action === 'focus_input') {
                      triggerComposerFocus()
                    } else {
                      selectOption(conversationId, message.id, opt.id, opt.label)
                    }
                  }}
                  className={cn(
                    'rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition-colors',
                    isSelected
                      ? 'border-[#10A37F] bg-[#10A37F]/10 text-[#0D8A6B]'
                      : hasSelection
                      ? 'border-[#E5E7EB] bg-[#F9F9F9] text-[#9CA3AF] cursor-default'
                      : 'border-[#E5E7EB] bg-white text-[#212121] hover:border-[#10A37F] hover:bg-[#F9F9F9]'
                  )}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        )}

        {/* Inline Production Shot Planner */}
        {planner && (
          <div className="space-y-3.5 pt-1">
            <ProjectOverview overview={planner.overview} />
            <CharacterSection characters={planner.characters} />
            <LocationSection locations={planner.locations} />

            <div ref={scenesTopRef} className="space-y-3 pt-1">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#212121]">
                  Scene-Wise Shot Breakdown
                </h3>
                {editNotice && (
                  <span className="text-xs font-medium text-[#10A37F]">
                    Click any shot below and choose &ldquo;Edit shot&rdquo; to refine it.
                  </span>
                )}
              </div>

              {planner.scenes.map((scene, index) => (
                <SceneAccordion
                  key={scene.sceneId}
                  plannerId={planner.id}
                  scene={scene}
                  defaultExpanded={index === 0}
                />
              ))}
            </div>

            <ApprovalPanel planner={planner} onRequestEdit={handleRequestEdit} />
          </div>
        )}

        {/* Message Footer Actions: Copy & Regenerate */}
        <div className="flex items-center gap-1 pt-0.5 text-[#6B7280]">
          <button
            type="button"
            onClick={handleCopy}
            title="Copy response"
            aria-label="Copy response"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors hover:bg-[#F1F1F1] hover:text-[#212121]"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-[#10A37F]" />
                <span className="text-[#10A37F]">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => regenerateAssistantMessage(conversationId, message.id)}
            title="Regenerate response"
            aria-label="Regenerate response"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors hover:bg-[#F1F1F1] hover:text-[#212121]"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Regenerate</span>
          </button>
        </div>
      </div>
    </motion.div>
  )
}
