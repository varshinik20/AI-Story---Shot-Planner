import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useChatStore } from '@/store/chatStore'
import { ChatWindow } from '@/components/chat/ChatWindow'
import { Button } from '@/components/ui/button'

export function ChatPage() {
  const { conversationId } = useParams<{ conversationId: string }>()
  const navigate = useNavigate()
  const { conversations, setActiveConversation } = useChatStore()

  const conversation = conversations.find((c) => c.id === conversationId)

  useEffect(() => {
      if (conversationId && conversation) {
        setActiveConversation(conversationId)
      }
}, [conversationId, conversation, setActiveConversation])

  // Show "not found" only if the store has conversations loaded but this one isn't among them.
  // If conversations is empty the store may still be hydrating — wait rather than 404.
  if (!conversationId || (conversations.length > 0 && !conversation)) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-4 text-center">
        <h2 className="text-lg font-semibold text-[#212121]">Conversation not found</h2>
        <p className="mt-1 text-sm text-[#6B7280]">
          This conversation may have been deleted from your local session.
        </p>
        <Button
          type="button"
          variant="outline"
          className="mt-4"
          onClick={() => navigate('/')}
        >
          Start a new chat
        </Button>
      </div>
    )
  }

  return <ChatWindow conversationId={conversationId} />
}
