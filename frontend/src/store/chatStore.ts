import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ChatMessage, Conversation, UploadedAttachment } from '@/types/chat'
import type { SuggestionStatus } from '@/types/story'
import type {
  IntakeFieldKey,
  StoryIntakeState,
} from '@/features/story-intake/types/storyIntake.types'
import { INITIAL_CONVERSATIONS, MOCK_PROJECTS } from '@/data/mockConversations'
import { generateId } from '@/lib/utils'
import {
  createInitialIntakeState,
  defaultStoryIntakeService,
} from '@/features/story-intake/services/storyIntakeService'
import {
  generateConfirmedStory,
  validateIntakeReadyForGeneration,
} from '@/features/story-intake/services/storyGenerationService'
import { storyIntakePersistence } from '@/features/story-intake/services/storyIntakePersistence'
import {
  sendChatTurn,
  uploadStoryFile,
  type BackendIntakeState,
} from '@/lib/api'
import { useProjectStore } from './projectStore'

function toLocalIntakeState(
  convId: string,
  projectId: string,
  backend: BackendIntakeState,
  readyForDev: boolean,
  needsConfirmation: boolean
): StoryIntakeState {
  const base = createInitialIntakeState(convId, projectId)
  return {
    ...base,
    storyTitle: {
      value: backend.story_title,
      provided: Boolean(backend.story_title),
      confirmed: backend.title_confirmed,
    },
    visualStyle: {
      value: backend.visual_style,
      provided: Boolean(backend.visual_style),
      confirmed: Boolean(backend.visual_style),
    },
    storyContext: {
      value: backend.story_context,
      provided: Boolean(backend.story_context),
      confirmed: Boolean(backend.story_context),
    },
    status: readyForDev
      ? 'ready_for_generation'
      : needsConfirmation
      ? 'awaiting_confirmation'
      : 'collecting',
    generationStarted: readyForDev,
    updatedAt: Date.now(),
  }
}

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
    targetConversationId?: string | null,
    options?: { inputSource?: 'text' | 'voice' }
  ) => Promise<string>

  selectOption: (
    conversationId: string,
    messageId: string,
    optionId: string,
    label: string
  ) => Promise<void>
  confirmStoryIntake: (conversationId: string, messageId: string) => Promise<void>
  requestEditStoryIntake: (
    conversationId: string,
    messageId: string,
    field?: IntakeFieldKey
  ) => void
  updateSuggestionStatus: (
    conversationId: string,
    messageId: string,
    suggestionId: string,
    status: SuggestionStatus
  ) => void
  regenerateAssistantMessage: (conversationId: string, messageId: string) => Promise<void>
  resetDemoData: () => void
}

function getEffectiveIntakeState(conv: Conversation): StoryIntakeState | null {
  return conv.intakeState ?? storyIntakePersistence.get(conv.id)
}

function isIntakeCompleteAndConfirmed(intake: StoryIntakeState | null): boolean {
  if (!intake) return false
  return (
    (intake.status === 'ready_for_generation' || intake.status === 'completed') &&
    intake.storyTitle.confirmed &&
    intake.visualStyle.confirmed &&
    intake.storyContext.confirmed &&
    Boolean(intake.storyTitle.value?.trim()) &&
    Boolean(intake.visualStyle.value?.trim()) &&
    Boolean(intake.storyContext.value?.trim())
  )
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

      deleteConversation: (id) => {
        storyIntakePersistence.remove(id)
        set((state) => ({
          conversations: state.conversations.filter((c) => c.id !== id),
          activeConversationId:
            state.activeConversationId === id ? null : state.activeConversationId,
        }))
      },

      triggerComposerFocus: (prefill) =>
        set((state) => ({
          focusComposerSignal: state.focusComposerSignal + 1,
          composerPrefill: prefill ?? null,
        })),

      clearComposerPrefill: () => set({ composerPrefill: null }),

      sendMessage: async (text, attachment, targetConversationId, options) => {
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
          inputSource: options?.inputSource ?? 'text',
          attachment,
        }

        if (!currentConv) {
          convId = generateId('conv')
          // Never invent a story title from an incomplete request like "give me a story"
          const initialSidebarTitle = attachment
            ? attachment.name.replace(/\.(pdf|txt|docx)$/i, '')
            : 'New Story'

          const initialIntake = createInitialIntakeState(convId, MOCK_PROJECTS[0].id)
          storyIntakePersistence.save(initialIntake)

          currentConv = {
            id: convId,
            title: initialSidebarTitle,
            projectId: MOCK_PROJECTS[0].id,
            createdAt: now,
            updatedAt: now,
            messages: [userMsg],
            storyDraft: {
              title: '',
              premise: '',
              segments: [],
            },
            interviewStep: 'idle',
            intakeState: initialIntake,
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

        const freshConv = get().conversations.find((c) => c.id === convId)
        if (!freshConv) {
          set({ isGenerating: false })
          return convId!
        }

        const existingIntake = getEffectiveIntakeState(freshConv)

        // LIVE MODE: Route typed text, voice transcripts, and document uploads through the unified FastAPI backend
        if (import.meta.env.MODE !== 'test') {
          try {
            if (attachment?.rawFile) {
              const up = await uploadStoryFile(attachment.rawFile, {
                projectId: freshConv.backendProjectId,
                conversationId: freshConv.backendConversationId,
              })
              const mappedIntake = toLocalIntakeState(
                freshConv.id,
                freshConv.projectId,
                up.intake_state,
                up.ready_for_story_development,
                up.needs_confirmation
              )
              storyIntakePersistence.save(mappedIntake)

              const assistantMsg: ChatMessage = {
                id: generateId('msg'),
                role: 'assistant',
                createdAt: Date.now(),
                content: up.assistant_message,
                showStyleSuggestions: up.style_options.length > 0,
                intakeConfirmation: up.needs_confirmation ? mappedIntake : undefined,
              }

              set((state) => ({
                isGenerating: false,
                conversations: state.conversations.map((c) =>
                  c.id !== convId
                    ? c
                    : {
                        ...c,
                        title: up.intake_state.story_title || c.title,
                        backendProjectId: up.project_id,
                        backendConversationId: up.conversation_id,
                        backendStoryId: up.story_id,
                        workflowStage: up.workflow_stage,
                        intakeState: mappedIntake,
                        updatedAt: Date.now(),
                        storyDraft: {
                          ...c.storyDraft,
                          title: up.intake_state.story_title || '',
                          visualStyle: up.intake_state.visual_style || undefined,
                          premise: up.extracted_text,
                        },
                        messages: [...c.messages, assistantMsg],
                      }
                ),
              }))
              return convId!
            }

            if (
              !freshConv.workflowStage ||
              freshConv.workflowStage === 'intake' ||
              freshConv.workflowStage === 'intake_confirmation'
            ) {
              const turnRes = await sendChatTurn({
                message: trimmed,
                input_source: options?.inputSource ?? 'text',
                project_id: freshConv.backendProjectId,
                conversation_id: freshConv.backendConversationId,
              })
              const mappedIntake = toLocalIntakeState(
                freshConv.id,
                freshConv.projectId,
                turnRes.intake_state,
                turnRes.ready_for_story_development,
                turnRes.needs_confirmation
              )
              storyIntakePersistence.save(mappedIntake)

              const titleOpts = turnRes.suggested_titles.map((label) => ({
                id: generateId('opt'),
                label,
                action: 'send' as const,
              }))
              const assistantMsg: ChatMessage = {
                id: generateId('msg'),
                role: 'assistant',
                createdAt: Date.now(),
                content: turnRes.assistant_message,
                showStyleSuggestions: turnRes.style_options.length > 0,
                intakeConfirmation: turnRes.needs_confirmation ? mappedIntake : undefined,
                options: titleOpts.length > 0 ? titleOpts : undefined,
              }

              set((state) => ({
                isGenerating: false,
                conversations: state.conversations.map((c) =>
                  c.id !== convId
                    ? c
                    : {
                        ...c,
                        title: turnRes.intake_state.story_title || c.title,
                        backendProjectId: turnRes.project_id,
                        backendConversationId: turnRes.conversation_id,
                        backendStoryId: turnRes.story_id ?? c.backendStoryId,
                        workflowStage: turnRes.workflow_stage,
                        intakeState: mappedIntake,
                        updatedAt: Date.now(),
                        storyDraft: {
                          ...c.storyDraft,
                          title: turnRes.intake_state.story_title || '',
                          visualStyle: turnRes.intake_state.visual_style || undefined,
                          premise: turnRes.intake_state.story_context || c.storyDraft.premise,
                        },
                        messages: [...c.messages, assistantMsg],
                      }
                ),
              }))
              return convId!
            }
          } catch (err) {
            const errMsg: ChatMessage = {
              id: generateId('msg'),
              role: 'assistant',
              createdAt: Date.now(),
              content:
                err instanceof Error
                  ? `Unable to process via backend AI service: ${err.message}`
                  : 'Unable to reach CINEMIND backend service.',
            }
            set((state) => ({
              isGenerating: false,
              conversations: state.conversations.map((c) =>
                c.id === convId
                  ? { ...c, updatedAt: Date.now(), messages: [...c.messages, errMsg] }
                  : c
              ),
            }))
            return convId!
          }
        }

        // PRIORITY 1: Every conversation without a confirmed intake state MUST pass through
        // the Adaptive Story Intake Controller BEFORE any story generation service runs.
        if (!isIntakeCompleteAndConfirmed(existingIntake)) {
          const currentIntake =
            existingIntake ?? createInitialIntakeState(freshConv.id, freshConv.projectId)

          const recentHistory = freshConv.messages
            .filter((m) => m.role === 'user' || m.role === 'assistant')
            .slice(-8)
            .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }))

          const effectiveMessage = attachment?.previewText
            ? trimmed
              ? `${trimmed}\n\n[Story from ${attachment.name}]:\n${attachment.previewText}`
              : `Story document (${attachment.name}):\n${attachment.previewText}`
            : trimmed || (attachment ? `Uploaded story document: ${attachment.name}` : '')

          const turn = await defaultStoryIntakeService.processUserMessage({
            conversationId: freshConv.id,
            projectId: freshConv.projectId,
            currentState: currentIntake,
            message: effectiveMessage,
            inputSource: options?.inputSource ?? 'text',
            hasAttachment: Boolean(attachment),
            attachmentName: attachment?.name,
            recentHistory,
          })

          // CASE 9: Explicit confirmation via chat message -> invoke story generation exactly once
          if (turn.shouldHandoffToGeneration) {
            const confirmedIntake = defaultStoryIntakeService.markConfirmed(
              freshConv.id,
              freshConv.projectId
            )

            const convForGeneration: Conversation = {
              ...freshConv,
              title: confirmedIntake.storyTitle.value || freshConv.title,
              intakeState: confirmedIntake,
              storyDraft: {
                ...freshConv.storyDraft,
                title: confirmedIntake.storyTitle.value || '',
                visualStyle: confirmedIntake.visualStyle.value || undefined,
                premise: confirmedIntake.storyContext.value || '',
              },
            }

            const aiData = await generateConfirmedStory({
              conversation: convForGeneration,
              intakeState: confirmedIntake,
            })

            if (aiData.planner) {
              useProjectStore.getState().registerPlanner(aiData.planner)
            }

            const assistantMessage: ChatMessage = {
              id: generateId('msg'),
              role: 'assistant',
              createdAt: Date.now(),
              content: aiData.content,
              options:
                aiData.options?.map((o) => ({
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
                  title: confirmedIntake.storyTitle.value || c.title,
                  updatedAt: Date.now(),
                  intakeState: confirmedIntake,
                  interviewStep: aiData.next_step,
                  plannerId: aiData.planner?.id ?? c.plannerId,
                  storyDraft: convForGeneration.storyDraft,
                  messages: [
                    ...c.messages.map((m) =>
                      m.intakeConfirmation
                        ? {
                          ...m,
                          intakeDecision: 'confirmed' as const,
                          intakeConfirmation: confirmedIntake,
                        }
                        : m
                    ),
                    assistantMessage,
                  ],
                }
              }),
            }))

            return convId!
          }

          const titleOptions = turn.titleOptions?.map((label) => ({
            id: generateId('opt'),
            label,
            action: 'send' as const,
          }))

          const intakeAssistantMessage: ChatMessage = {
            id: generateId('msg'),
            role: 'assistant',
            createdAt: Date.now(),
            content: turn.assistantContent,
            showStyleSuggestions: turn.includeStyleSuggestions,
            intakeConfirmation: turn.showConfirmationCard ? turn.state : undefined,
            options: titleOptions,
          }

          set((state) => ({
            isGenerating: false,
            conversations: state.conversations.map((c) => {
              if (c.id !== convId) return c
              const resolvedTitle = turn.state.storyTitle.value || c.title
              return {
                ...c,
                title: resolvedTitle,
                updatedAt: Date.now(),
                intakeState: turn.state,
                storyDraft: {
                  ...c.storyDraft,
                  title: turn.state.storyTitle.value || '',
                  visualStyle: turn.state.visualStyle.value || c.storyDraft.visualStyle,
                  premise: turn.state.storyContext.value || c.storyDraft.premise,
                },
                messages: [...c.messages, intakeAssistantMessage],
              }
            }),
          }))

          return convId!
        }

        // PRIORITY 2: Confirmed story -> validate intake gate independently before generation
        validateIntakeReadyForGeneration(existingIntake)

        const aiData = await generateConfirmedStory({
          conversation: freshConv,
          intakeState: existingIntake,
        })

        if (aiData.planner) {
          useProjectStore.getState().registerPlanner(aiData.planner)
        }

        const assistantMessage: ChatMessage = {
          id: generateId('msg'),
          role: 'assistant',
          createdAt: Date.now(),
          content: aiData.content,
          options:
            aiData.options?.map((o) => ({
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
              title: existingIntake.storyTitle.value || aiData.suggested_title || c.title,
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

      confirmStoryIntake: async (conversationId, messageId) => {
        const conv = get().conversations.find((c) => c.id === conversationId)
        if (!conv) return

        const currentIntake = getEffectiveIntakeState(conv)
        if (currentIntake?.generationStarted) {
          return
        }

        const confirmedIntake = defaultStoryIntakeService.markConfirmed(
          conversationId,
          conv.projectId
        )

        const userConfirmMsg: ChatMessage = {
          id: generateId('msg'),
          role: 'user',
          content: 'Confirm and develop.',
          createdAt: Date.now(),
        }

        const updatedDraft = {
          ...conv.storyDraft,
          title: confirmedIntake.storyTitle.value || '',
          visualStyle: confirmedIntake.visualStyle.value || conv.storyDraft.visualStyle,
          premise: confirmedIntake.storyContext.value || conv.storyDraft.premise,
        }

        const convWithConfirm: Conversation = {
          ...conv,
          title: confirmedIntake.storyTitle.value || conv.title,
          intakeState: confirmedIntake,
          storyDraft: updatedDraft,
          messages: [
            ...conv.messages.map((m) =>
              m.id === messageId
                ? {
                  ...m,
                  intakeDecision: 'confirmed' as const,
                  intakeConfirmation: confirmedIntake,
                }
                : m
            ),
            userConfirmMsg,
          ],
        }

        set((state) => ({
          isGenerating: true,
          conversations: state.conversations.map((c) =>
            c.id === conversationId ? convWithConfirm : c
          ),
        }))

        if (import.meta.env.MODE !== 'test' && conv.backendConversationId) {
          try {
            const confirmRes = await sendChatTurn({
              message: 'Yes, looks good',
              input_source: 'text',
              project_id: conv.backendProjectId,
              conversation_id: conv.backendConversationId,
            })
            const assistantReply: ChatMessage = {
              id: generateId('msg'),
              role: 'assistant',
              createdAt: Date.now(),
              content: confirmRes.assistant_message,
            }
            set((state) => ({
              isGenerating: false,
              conversations: state.conversations.map((c) =>
                c.id === conversationId
                  ? {
                      ...c,
                      backendProjectId: confirmRes.project_id,
                      backendConversationId: confirmRes.conversation_id,
                      backendStoryId: confirmRes.story_id ?? c.backendStoryId,
                      workflowStage: confirmRes.workflow_stage,
                      updatedAt: Date.now(),
                      messages: [...c.messages, assistantReply],
                    }
                  : c
              ),
            }))
            return
          } catch {
            // Fall through cleanly if offline
          }
        }

        const aiData = await generateConfirmedStory({
          conversation: convWithConfirm,
          intakeState: confirmedIntake,
        })

        if (aiData.planner) {
          useProjectStore.getState().registerPlanner(aiData.planner)
        }

        const generatedMsg: ChatMessage = {
          id: generateId('msg'),
          role: 'assistant',
          createdAt: Date.now(),
          content: aiData.content,
          options:
            aiData.options?.map((o) => ({
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
            if (c.id !== conversationId) return c
            return {
              ...c,
              updatedAt: Date.now(),
              interviewStep: aiData.next_step,
              plannerId: aiData.planner?.id ?? c.plannerId,
              messages: [...c.messages, generatedMsg],
            }
          }),
        }))
      },

      requestEditStoryIntake: (conversationId, messageId, field) => {
        const conv = get().conversations.find((c) => c.id === conversationId)
        if (!conv) return

        const updatedIntake = field
          ? defaultStoryIntakeService.markFieldEdit(conversationId, conv.projectId, field)
          : defaultStoryIntakeService.requestEdit(conversationId, conv.projectId)

        const promptByField: Record<IntakeFieldKey, string> = {
          story_title: 'What would you like to change the **story title** to?',
          visual_style:
            'What **visual style** would you like instead? You can pick an option below or describe your own direction.',
          story_context: 'How would you like to update the **story context**?',
        }

        const promptMsg: ChatMessage = {
          id: generateId('msg'),
          role: 'assistant',
          createdAt: Date.now(),
          content: field
            ? promptByField[field]
            : 'Of course—tell me which detail you want to update (title, visual style, or story context), and I will preserve everything else.',
          showStyleSuggestions: field === 'visual_style',
        }

        set((state) => ({
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c
            return {
              ...c,
              updatedAt: Date.now(),
              intakeState: updatedIntake,
              messages: [
                ...c.messages.map((m) =>
                  m.id === messageId ? { ...m, intakeDecision: 'editing' as const } : m
                ),
                promptMsg,
              ],
            }
          }),
        }))
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
          ? targetMsg.content.replace(
            /\n\n\*Refined perspective:\*[\s\S]*$/,
            alternateVariations[1]
          )
          : `${targetMsg.content}${alternateVariations[0]}`

        set((state) => ({
          isGenerating: false,
          conversations: state.conversations.map((c) => {
            if (c.id !== conversationId) return c
            return {
              ...c,
              updatedAt: Date.now(),
              messages: c.messages.map((m) =>
                m.id === messageId
                  ? { ...m, content: nextContent, createdAt: Date.now() }
                  : m
              ),
            }
          }),
        }))
      },

      resetDemoData: () => {
        storyIntakePersistence.clearAll()
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
