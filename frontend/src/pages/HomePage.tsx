import { useEffect } from 'react'
import { useChatStore } from '@/store/chatStore'
import { ChatWindow } from '@/components/chat/ChatWindow'

export function HomePage() {
  const setActiveConversation = useChatStore((s) => s.setActiveConversation)

  useEffect(() => {
    setActiveConversation(null)
  }, [setActiveConversation])

  return <ChatWindow />
}
