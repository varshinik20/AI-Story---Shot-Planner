import { useNavigate } from 'react-router-dom'
import { Menu, PanelLeftOpen, SquarePen } from 'lucide-react'
import { useChatStore } from '@/store/chatStore'

interface TopbarProps {
  onOpenMobileSidebar: () => void
}

export function Topbar({ onOpenMobileSidebar }: TopbarProps) {
  const navigate = useNavigate()
  const {
    sidebarOpen,
    setSidebarOpen,
    conversations,
    activeConversationId,
    createNewChat,
  } = useChatStore()

  const activeConv = conversations.find((c) => c.id === activeConversationId)

  const handleNewChat = () => {
    createNewChat()
    navigate('/')
  }

  return (
    <header className="flex h-[52px] shrink-0 items-center justify-between border-b border-[#E5E7EB]/70 bg-white px-3 sm:px-4">
      <div className="flex min-w-0 items-center gap-2">
        {/* Mobile Hamburger */}
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          aria-label="Open menu"
          className="rounded-lg p-1.5 text-[#6B7280] transition-colors hover:bg-[#F1F1F1] hover:text-[#212121] md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Desktop Expand Sidebar (shown when collapsed) */}
        {!sidebarOpen && (
          <div className="hidden items-center gap-1 md:flex">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              title="Expand sidebar"
              aria-label="Expand sidebar"
              className="rounded-lg p-1.5 text-[#6B7280] transition-colors hover:bg-[#F1F1F1] hover:text-[#212121]"
            >
              <PanelLeftOpen className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={handleNewChat}
              title="New chat"
              aria-label="New chat"
              className="rounded-lg p-1.5 text-[#6B7280] transition-colors hover:bg-[#F1F1F1] hover:text-[#212121]"
            >
              <SquarePen className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Title / Current Project */}
        <div className="flex min-w-0 items-center gap-2 px-1">
          <span className="text-[15px] font-semibold tracking-tight text-[#212121]">
            StoryForge
          </span>
          <span className="hidden rounded-full border border-[#E5E7EB] bg-[#F9F9F9] px-2 py-0.5 text-[11px] font-medium text-[#6B7280] sm:inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[#10A37F]" />
            Story &amp; Shot Planner
          </span>
          {activeConv && (
            <>
              <span className="hidden text-[#D1D5DB] sm:inline">/</span>
              <span className="hidden max-w-[240px] truncate text-sm text-[#6B7280] sm:inline">
                {activeConv.title}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Right Action */}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={handleNewChat}
          title="New chat"
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-[#6B7280] transition-colors hover:bg-[#F1F1F1] hover:text-[#212121] md:hidden"
        >
          <SquarePen className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}
