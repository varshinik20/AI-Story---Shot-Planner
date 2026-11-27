import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ChatMessage, Conversation, UploadedAttachment } from '@/types/chat'
import type { SuggestionStatus } from '@/types/story'
import { INITIAL_CONVERSATIONS, MOCK_PROJECTS } from '@/data/mockConversations'
import { sendAIChat } from '@/lib/api'
import { generateId } from '@/lib/utils'
import { useProjectStore } from './projectStore'

interface ChatState {
  conversations: Conversation[]
  activeConversationId: string | null
  searchQuery: string
  sidebarOpen: boolean
  isGenerating: boolean
  focusComposerSignal: number
  composerPrefill: string | null

  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void
  setSearchQuery: (query: string) => void
  setActiveConversation: (id: string | null) => void
  createNewChat: () => void
  deleteConversation: (id: string) => void
  triggerComposerFocus: (prefill?: string) => void
  clearComposerPrefill: () => void

  sendMessage: (
    text: string,
    attachment?: UploadedAttachment,
    targetConversationId?: string | null
  ) => Promise<string>

  selectOption: (conversationId: string, messageId: string, optionId: string, label: string) => Promise<void>
  updateSuggestionStatus: (
    conversationId: string,
    messageId: string,
    suggestionId: string,
    status: SuggestionStatus
  ) => void
  regenerateAssistantMessage: (conversationId: string, messageId: string) => Promise<void>
  resetDemoData: () => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      conversations: INITIAL_CONVERSATIONS,
      activeConversationId: null,
      searchQuery: '',
      sidebarOpen: true,
      isGenerating: false,
      focusComposerSignal: 0,
      composerPrefill: null,

      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSearchQuery: (searchQuery) => set({ searchQuery }),
      setActiveConversation: (id) => set({ activeConversationId: id }),

      createNewChat: () => set({ activeConversationId: null }),

      deleteConversation: (id) =>
        set((state) => ({
          conversations: state.conversations.filter((c) => c.id !== id),
          activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
        })),

      triggerComposerFocus: (prefill) =>
        set((state) => ({
          focusComposerSignal: state.focusComposerSignal + 1,
          composerPrefill: prefill ?? null,
        })),

      clearComposerPrefill: () => set({ composerPrefill: null }),

      sendMessage: async (text, attachment, targetConversationId) => {
        const trimmed = text.trim()
        if (!trimmed && !attachment) {
          return get().activeConversationId || ''
        }

        const now = Date.now()
        let convId = targetConversationId ?? get().activeConversationId
        let currentConv = get().conversations.find((c) => c.id === convId)

        const userMsg: ChatMessage = {
          id: generateId('msg'),
          role: 'user',
          content: trimmed || (attachment ? `Uploaded story document: ${attachment.name}` : ''),
          createdAt: now,
          attachment,
        }

        if (!currentConv) {
          convId = generateId('conv')
          const initialTitle = attachment
            ? attachment.name.replace(/\.(pdf|txt|docx)$/i, '')
            : trimmed.length > 42
              ? `${trimmed.slice(0, 42)}...`
              : trimmed

          currentConv = {
            id: convId,
            title: initialTitle,
            projectId: MOCK_PROJECTS[0].id,
            createdAt: now,
            updatedAt: now,
            messages: [userMsg],
            storyDraft: {
              title: initialTitle,
              premise: trimmed,
              segments: trimmed ? [trimmed] : [],
            },
            interviewStep: 'idle',
          }

          set((state) => ({
            conversations: [currentConv!, ...state.conversations],
            activeConversationId: convId,
            isGenerating: true,
          }))
        } else {
          set((state) => ({
            conversations: state.conversations.map((c) =>
              c.id === convId
                ? {
                  ...c,
                  updatedAt: now,
                  messages: [...c.messages, userMsg],
                }
                : c
            ),
            isGenerating: true,
          }))
        }

        // Call the real CINEMIND backend AI endpoint
        const freshConv = get().conversations.find((c) => c.id === convId)
        if (!freshConv) {
          set({ isGenerating: false })
          return convId!
        }

        // Build the message history for the AI (last 20 messages to stay within context)
        const historyForAI = freshConv.messages
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .slice(-20)
          .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }))

          let aiData
          try {
            aiData = await sendAIChat({
              messages: historyForAI,
              interview_step: freshConv.interviewStep,
              story_draft: freshConv.storyDraft as Record<string, unknown>,
            })
          } catch (err) {
            console.error('AI chat error:', err)
            set((state) => ({
              isGenerating: false,
              conversations: state.conversations.map((c) =>
                c.id !== convId
                  ? c
                  : {
                    ...c,
                    messages: [
                      ...c.messages,
                      {
                        id: generateId('msg'),
                        role: 'assistant' as const,
                        content: `⚠️ Could not reach the CINEMIND AI backend. Make sure the server is running at \`http://127.0.0.1:8000\` and your \`OPENAI_API_KEY\` is set in \`backend/.env\`.\n\nError: ${String(err)}`,
                        createdAt: Date.now(),
                      },
                    ],
                  }
              ),
            }))
            return convId!
          }

          // If the AI returned a planner, register it in the project store
          if (aiData.planner) {
            useProjectStore.getState().registerPlanner(aiData.planner)
          }

          const assistantMessage: ChatMessage = {
            id: generateId('msg'),
            role: 'assistant',
            createdAt: Date.now(),
            content: aiData.content,
            options: aiData.options?.map((o) => ({
              ...o,
              id: o.id || generateId('opt'),
              action: (o.action as 'send' | 'focus_input') ?? 'send',
            })) ?? undefined,
            plannerId: aiData.planner?.id,
            isApprovalCard: !!aiData.planner,
          }

          set((state) => ({
            isGenerating: false,
            conversations: state.conversations.map((c) => {
              if (c.id !== convId) return c
              return {
                ...c,
                title: aiData.suggested_title || c.title,
                updatedAt: Date.now(),
                interviewStep: aiData.next_step,
                plannerId: aiData.planner?.id ?? c.plannerId,
                storyDraft: { ...c.storyDraft },
                messages: [...c.messages, assistantMessage],
              }
            }),
          }))

          return convId!
        },

        selectOption: async (conversationId, messageId, optionId, label) => {
          set((state) => ({
            conversations: state.conversations.map((c) => {
              if (c.id !== conversationId) return c
              return {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === messageId ? { ...m, selectedOptionId: optionId } : m
                ),
              }
            }),
          }))

          await get().sendMessage(label, undefined, conversationId)
        },

          updateSuggestionStatus: (conversationId, messageId, suggestionId, status) =>
            set((state) => ({
              conversations: state.conversations.map((c) => {
                if (c.id !== conversationId) return c

                let acceptedSegment: string | null = null
                const updatedMessages = c.messages.map((m) => {
                  if (m.id !== messageId || !m.suggestions) return m
                  return {
                    ...m,
                    suggestions: m.suggestions.map((sug) => {
                      if (sug.id !== suggestionId) return sug
                      if (status === 'accepted') {
                        acceptedSegment = sug.suggestedImprovement
                      }
                      return { ...sug, status }
                    }),
                  }
                })

                const updatedSegments = acceptedSegment
                  ? [...c.storyDraft.segments, acceptedSegment]
                  : c.storyDraft.segments

                return {
                  ...c,
                  updatedAt: Date.now(),
                  storyDraft: {
                    ...c.storyDraft,
                    segments: updatedSegments,
                  },
                  messages: updatedMessages,
                }
              }),
            })),

            regenerateAssistantMessage: async (conversationId, messageId) => {
              const conv = get().conversations.find((c) => c.id === conversationId)
              if (!conv) return

              const msgIndex = conv.messages.findIndex((m) => m.id === messageId)
              if (msgIndex === -1) return

              const targetMsg = conv.messages[msgIndex]
              if (targetMsg.role !== 'assistant') return

              set({ isGenerating: true })
              await new Promise((resolve) => setTimeout(resolve, 600))

              const alternateVariations = [
                "\n\n*Refined perspective:* Consider heightening the contrast between ambient silence and one sharp sensory cue right before the beat turns.",
                "\n\n*Director's note:* Pacing this moment with a beat of stillness lets the audience anticipate the emotional shift before any dialogue lands.",
              ]

              const hasSuffix = targetMsg.content.includes('*Refined perspective:*')
              const nextContent = hasSuffix
                ? targetMsg.content.replace(/\n\n\*Refined perspective:\*[\s\S]*$/, alternateVariations[1])
                : `${targetMsg.content}${alternateVariations[0]}`

              set((state) => ({
                isGenerating: false,
                conversations: state.conversations.map((c) => {
                  if (c.id !== conversationId) return c
                  return {
                    ...c,
                    updatedAt: Date.now(),
                    messages: c.messages.map((m) =>
                      m.id === messageId ? { ...m, content: nextContent, createdAt: Date.now() } : m
                    ),
                  }
                }),
              }))
            },

              resetDemoData: () => {
                useProjectStore.getState().resetPlanners()
                set({
                  conversations: INITIAL_CONVERSATIONS,
                  activeConversationId: null,
                  searchQuery: '',
                  isGenerating: false,
                })
              },
    }),
    {
      name: 'storyforge_chats_v1',
      partialize: (state) => ({
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
        sidebarOpen: state.sidebarOpen,
      }),
    }
  )
)
