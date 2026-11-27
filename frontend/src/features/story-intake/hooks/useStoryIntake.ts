import { useCallback, useMemo } from 'react'
import { useChatStore } from '@/store/chatStore'
import type { IntakeFieldKey, StoryIntakeState } from '../types/storyIntake.types'
import { storyIntakePersistence } from '../services/storyIntakePersistence'

export function useStoryIntake(conversationId?: string) {
  const {
    conversations,
    confirmStoryIntake,
    requestEditStoryIntake,
    triggerComposerFocus,
  } = useChatStore()

  const conversation = useMemo(
    () => (conversationId ? conversations.find((c) => c.id === conversationId) : undefined),
    [conversationId, conversations]
  )

  const intakeState: StoryIntakeState | null = useMemo(() => {
    if (!conversationId) return null
    return conversation?.intakeState ?? storyIntakePersistence.get(conversationId)
  }, [conversation?.intakeState, conversationId])

  const confirm = useCallback(
    async (messageId: string) => {
      if (!conversationId) return
      await confirmStoryIntake(conversationId, messageId)
    },
    [confirmStoryIntake, conversationId]
  )

  const requestEdit = useCallback(
    (messageId: string, field?: IntakeFieldKey) => {
      if (!conversationId) return
      requestEditStoryIntake(conversationId, messageId, field)
      triggerComposerFocus()
    },
    [conversationId, requestEditStoryIntake, triggerComposerFocus]
  )

  return {
    intakeState,
    confirm,
    requestEdit,
  }
}
