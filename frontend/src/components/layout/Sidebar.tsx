import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FolderKanban,
  MessageSquare,
  PanelLeftClose,
  Plus,
  RotateCcw,
  Search,
  Settings,
  Trash2,
  User,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/store/chatStore'
import { useProjectStore } from '@/store/projectStore'
import { MOCK_PROJECTS } from '@/data/mockConversations'
import { StoryForgeLogo } from '@/components/common/StoryForgeLogo'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface SidebarProps {
  mobileOpen: boolean
  onCloseMobile: () => void
}

export function Sidebar({ mobileOpen, onCloseMobile }: SidebarProps) {
  const navigate = useNavigate()
  const {
    conversations,
    activeConversationId,
    searchQuery,
    sidebarOpen,
    setSidebarOpen,
    setSearchQuery,
    setActiveConversation,
    createNewChat,
    deleteConversation,
    resetDemoData,
  } = useChatStore()

  const { defaultVideoFormat, defaultFrameRate, setDefaults } = useProjectStore()

  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const [formatDraft, setFormatDraft] = useState(defaultVideoFormat)
  const [fpsDraft, setFpsDraft] = useState(defaultFrameRate)

  const filteredConversations = useMemo(() => {
    return conversations.filter((conv) => {
      const matchesProject = selectedProjectId ? conv.projectId === selectedProjectId : true
      const q = searchQuery.trim().toLowerCase()
      if (!q) return matchesProject
      const matchesTitle = conv.title.toLowerCase().includes(q)
      const matchesMessages = conv.messages.some((m) => m.content.toLowerCase().includes(q))
      return matchesProject && (matchesTitle || matchesMessages)
    })
  }, [conversations, searchQuery, selectedProjectId])

  const handleNewChat = () => {
    createNewChat()
    navigate('/')
    onCloseMobile()
  }

  const handleSelectConversation = (id: string) => {
    setActiveConversation(id)
    navigate(`/c/${id}`)
    onCloseMobile()
  }

  const deleteTarget = conversations.find((c) => c.id === deleteTargetId)

  const sidebarBody = (
    <div className="flex h-full w-[260px] flex-col border-r border-[#E5E7EB] bg-[#F9F9F9] text-[#212121]">
      {/* Header: Logo + Collapse */}
      <div className="flex h-[52px] items-center justify-between px-3">
        <button
          type="button"
          onClick={handleNewChat}
          className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-[#F1F1F1]"
        >
          <StoryForgeLogo className="h-6 w-6" />
          <span className="text-[15px] font-semibold tracking-tight text-[#212121]">
            StoryForge
          </span>
        </button>

        <button
          type="button"
          onClick={() => {
            if (mobileOpen) {
              onCloseMobile()
            } else {
              setSidebarOpen(false)
            }
          }}
          title="Collapse sidebar"
          aria-label="Collapse sidebar"
          className="rounded-lg p-1.5 text-[#6B7280] transition-colors hover:bg-[#F1F1F1] hover:text-[#212121]"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      {/* New Chat Button */}
      <div className="px-2.5 pt-1">
        <button
          type="button"
          onClick={handleNewChat}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-[#212121] transition-colors hover:bg-[#F1F1F1]"
        >
          <Plus className="h-4 w-4 text-[#212121]" />
          <span>New chat</span>
        </button>
      </div>

      {/* Search Input */}
      <div className="px-2.5 py-2">
        <div className="relative flex items-center">
          <Search className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-[#6B7280]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white pl-8 pr-7 text-xs text-[#212121] placeholder:text-[#6B7280] focus:border-[#10A37F] focus:outline-none"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              aria-label="Clear search"
              className="absolute right-2 rounded p-0.5 text-[#6B7280] hover:text-[#212121]"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      {/* Scrollable Navigation: Projects + Recent */}
      <div className="flex-1 overflow-y-auto px-2.5 py-1">
        {/* Projects Section */}
        <div className="mb-4">
          <div className="px-2.5 pb-1.5 pt-1 text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Projects
          </div>
          {MOCK_PROJECTS.map((project) => {
            const isSelected = selectedProjectId === project.id
            return (
              <button
                key={project.id}
                type="button"
                onClick={() => setSelectedProjectId(isSelected ? null : project.id)}
                className={cn(
                  'flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm transition-colors',
                  isSelected
                    ? 'bg-[#ECECEC] font-medium text-[#212121]'
                    : 'text-[#212121] hover:bg-[#F1F1F1]'
                )}
              >
                <span className="flex items-center gap-2.5 truncate">
                  <FolderKanban className="h-4 w-4 shrink-0 text-[#6B7280]" />
                  <span className="truncate">{project.name}</span>
                </span>
                <span className="text-[11px] text-[#6B7280]">{conversations.length}</span>
              </button>
            )
          })}
        </div>

        {/* Recent Section */}
        <div>
          <div className="flex items-center justify-between px-2.5 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            <span>Recent</span>
            {selectedProjectId && (
              <button
                type="button"
                onClick={() => setSelectedProjectId(null)}
                className="text-[10px] font-normal normal-case text-[#10A37F] hover:underline"
              >
                Show all
              </button>
            )}
          </div>

          {filteredConversations.length === 0 ? (
            <p className="px-2.5 py-3 text-xs text-[#6B7280]">No matching conversations.</p>
          ) : (
            <ul className="space-y-0.5">
              {filteredConversations.map((conv) => {
                const isActive = conv.id === activeConversationId
                return (
                  <li key={conv.id} className="group relative">
                    <button
                      type="button"
                      onClick={() => handleSelectConversation(conv.id)}
                      className={cn(
                        'flex w-full items-center gap-2.5 rounded-lg py-2 pl-2.5 pr-8 text-left text-sm transition-colors',
                        isActive
                          ? 'bg-[#ECECEC] font-medium text-[#212121]'
                          : 'text-[#212121] hover:bg-[#F1F1F1]'
                      )}
                    >
                      <MessageSquare className="h-3.5 w-3.5 shrink-0 text-[#6B7280]" />
                      <span className="truncate">{conv.title}</span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeleteTargetId(conv.id)
                      }}
                      title="Delete conversation"
                      aria-label={`Delete ${conv.title}`}
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-[#6B7280] opacity-0 transition-opacity hover:bg-[#E5E7EB] hover:text-red-600 group-hover:opacity-100 focus:opacity-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>

      {/* Bottom Profile & Settings */}
      <div className="border-t border-[#E5E7EB] p-2.5 space-y-0.5">
        <button
          type="button"
          onClick={() => setProfileOpen(true)}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-[#212121] transition-colors hover:bg-[#F1F1F1]"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#212121] text-[11px] font-semibold text-white">
            SF
          </span>
          <span className="truncate font-medium">User account</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setFormatDraft(defaultVideoFormat)
            setFpsDraft(defaultFrameRate)
            setSettingsOpen(true)
          }}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-[#6B7280] transition-colors hover:bg-[#F1F1F1] hover:text-[#212121]"
        >
          <Settings className="h-4 w-4 shrink-0" />
          <span>Settings</span>
        </button>
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop Collapsible Sidebar */}
      <aside
        className={cn(
          'hidden md:block shrink-0 overflow-hidden transition-[width] duration-200 ease-in-out',
          sidebarOpen ? 'w-[260px]' : 'w-0'
        )}
      >
        {sidebarOpen && sidebarBody}
      </aside>

      {/* Mobile Slide-out Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/30"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <div className="relative z-10 h-full">{sidebarBody}</div>
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={Boolean(deleteTargetId)}
        onOpenChange={(open) => {
          if (!open) setDeleteTargetId(null)
        }}
        title="Delete conversation?"
        description={`This will permanently remove "${deleteTarget?.title || ''}" from your local conversation history.`}
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          if (deleteTargetId) {
            const wasActive = deleteTargetId === activeConversationId
            deleteConversation(deleteTargetId)
            if (wasActive) navigate('/')
          }
        }}
      />

      {/* User Account Modal */}
      <Dialog open={profileOpen} onOpenChange={setProfileOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Creator Account</DialogTitle>
            <DialogDescription>
              Local StoryForge workspace session (persisted in browser storage).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 pt-1 text-sm">
            <div className="flex items-center gap-3 rounded-xl border border-[#E5E7EB] bg-[#F9F9F9] p-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#10A37F] text-white">
                <User className="h-5 w-5" />
              </div>
              <div>
                <p className="font-medium text-[#212121]">StoryForge Creator</p>
                <p className="text-xs text-[#6B7280]">Hackathon Demo Mode • No API key required</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg border border-[#E5E7EB] p-3">
                <p className="text-[#6B7280]">Saved Conversations</p>
                <p className="mt-0.5 text-base font-semibold text-[#212121]">
                  {conversations.length}
                </p>
              </div>
              <div className="rounded-lg border border-[#E5E7EB] p-3">
                <p className="text-[#6B7280]">Storage</p>
                <p className="mt-0.5 text-base font-semibold text-[#212121]">localStorage</p>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Settings Modal */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>StoryForge Settings</DialogTitle>
            <DialogDescription>
              Configure default shot plan specifications or reset demo conversations.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-1 text-sm">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[#212121]">Default Video Format</label>
              <select
                value={formatDraft}
                onChange={(e) => setFormatDraft(e.target.value)}
                className="h-9 w-full rounded-lg border border-[#E5E7EB] bg-white px-3 text-sm text-[#212121] focus:border-[#10A37F] focus:outline-none"
              >
                <option value="16:9 (1920x1080 HD)">16:9 (1920x1080 HD)</option>
                <option value="2.39:1 Anamorphic">2.39:1 Anamorphic</option>
                <option value="9:16 Vertical Short">9:16 Vertical Short</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[#212121]">Default Frame Rate</label>
              <select
                value={fpsDraft}
                onChange={(e) => setFpsDraft(e.target.value)}
                className="h-9 w-full rounded-lg border border-[#E5E7EB] bg-white px-3 text-sm text-[#212121] focus:border-[#10A37F] focus:outline-none"
              >
                <option value="24 fps">24 fps (Cinema)</option>
                <option value="30 fps">30 fps (Broadcast)</option>
                <option value="60 fps">60 fps (High Frame Rate)</option>
              </select>
            </div>

            <div className="flex items-center justify-between border-t border-[#E5E7EB] pt-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  resetDemoData()
                  setSettingsOpen(false)
                  navigate('/')
                }}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Reset demo data
              </Button>
              <Button
                type="button"
                variant="accent"
                size="sm"
                onClick={() => {
                  setDefaults(formatDraft, fpsDraft)
                  setSettingsOpen(false)
                }}
              >
                Save preferences
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
