import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'
import { StoryForgeLogo } from '@/components/common/StoryForgeLogo'
import { LoadingIndicator } from '@/components/common/LoadingIndicator'
import { SuggestionChips } from './SuggestionChips'
import { MessageBubble } from './MessageBubble'
import { ChatComposer } from './ChatComposer'

interface ChatWindowProps {
  conversationId?: string
}

export function ChatWindow({ conversationId }: ChatWindowProps) {
  const navigate = useNavigate()
  const {
    conversations,
    isGenerating,
    sendMessage,
    setActiveConversation,
    activeConversationId,
  } = useChatStore()

  const bottomRef = useRef<HTMLDivElement>(null)
  const activeConv = conversationId
    ? conversations.find((c) => c.id === conversationId)
    : undefined

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeConv?.messages.length, isGenerating])

  // When a NEW conversation is created from the home page, navigate to it immediately
  // as soon as it appears in the store — don't wait for the AI response.
  useEffect(() => {
    if (!conversationId && activeConversationId) {
      navigate(`/c/${activeConversationId}`, { replace: true })
    }
  }, [conversationId, activeConversationId, navigate])

  const handleSend = async (
    text: string,
    attachment?: Parameters<typeof sendMessage>[1],
    options?: { inputSource?: 'text' | 'voice' }
  ) => {
    await sendMessage(text, attachment, conversationId ?? null, options)
    // Navigation is handled by the useEffect above reacting to activeConversationId change
  }

  const handleOpenDemo = () => {
    setActiveConversation('conv_boy_who_cried_wolf')
    navigate('/c/conv_boy_who_cried_wolf')
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      {/* Scrollable Conversation Area or Centered Welcome Screen */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6">
        {!activeConv ? (
          <div className="mx-auto flex min-h-full max-w-3xl flex-col items-center justify-center py-10 text-center">
            <StoryForgeLogo className="mb-4 h-10 w-10" />
            <h1 className="text-2xl font-semibold tracking-tight text-[#212121] sm:text-[28px]">
              What story are we creating today?
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-[#6B7280] sm:text-[15px]">
              Turn your imagination into a complete story, cinematic scenes and production-ready shots.
            </p>

            <SuggestionChips onSelect={(prompt) => handleSend(prompt)} />

            <div className="mt-6">
              <button
                type="button"
                onClick={handleOpenDemo}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#E5E7EB] bg-[#F9F9F9] px-3.5 py-1.5 text-xs font-medium text-[#212121] transition-colors hover:bg-[#F1F1F1]"
              >
                <span>Explore demo project: The Boy Who Cried Wolf (3 scenes, 17 shots)</span>
                <ArrowRight className="h-3.5 w-3.5 text-[#10A37F]" />
              </button>
            </div>
          </div>
        ) : (
          <div className="mx-auto w-full max-w-3xl py-6">
            {activeConv.messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                conversationId={activeConv.id}
                message={msg}
              />
            ))}

            {isGenerating && <LoadingIndicator />}
            <div ref={bottomRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Bottom Fixed Composer */}
      <ChatComposer
        onSend={handleSend}
        disabled={isGenerating}
        conversationId={conversationId}
      />
    </div>
  )
}
