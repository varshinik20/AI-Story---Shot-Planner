import { useState } from 'react'
import { ChevronDown, ChevronRight, Pencil, RefreshCw } from 'lucide-react'
import type { Shot } from '@/types/planner'
import { useProjectStore } from '@/store/projectStore'
import { ShotEditor, ShotRegenerateBox } from './ShotEditor'

interface ShotCardProps {
  plannerId: string
  sceneId: string
  shot: Shot
  defaultExpanded?: boolean
}

export function ShotCard({
  plannerId,
  sceneId,
  shot,
  defaultExpanded = false,
}: ShotCardProps) {
  const { updateShot, regenerateShot } = useProjectStore()
  const [expanded, setExpanded] = useState(defaultExpanded)
  const [isEditing, setIsEditing] = useState(false)
  const [showRegen, setShowRegen] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)

  const handleRegenerate = (feedback: string) => {
    setIsRegenerating(true)
    setTimeout(() => {
      regenerateShot(plannerId, sceneId, shot.shotId, feedback)
      setIsRegenerating(false)
      setShowRegen(false)
      setExpanded(true)
    }, 550)
  }

  return (
    <div className="rounded-xl border border-[#E5E7EB] bg-white transition-colors">
      {/* Compact Header Row */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left transition-colors hover:bg-[#F9F9F9]"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[#6B7280]" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[#6B7280]" />
          )}
          <span className="shrink-0 rounded-md bg-[#F4F4F4] px-2 py-0.5 font-mono text-[11px] font-semibold text-[#212121]">
            {shot.shotId}
          </span>
          <span className="truncate text-[13px] text-[#212121]">{shot.whatWeSee}</span>
        </div>

        <div className="flex shrink-0 items-center gap-2 text-[11px] text-[#6B7280]">
          <span className="hidden rounded border border-[#E5E7EB] px-1.5 py-0.5 sm:inline">
            {shot.framing}
          </span>
          <span className="font-medium text-[#212121]">{shot.durationSeconds}s</span>
        </div>
      </button>

      {/* Expanded 10-Field Breakdown or Editor */}
      {expanded && (
        <div className="border-t border-[#E5E7EB] px-3.5 py-3">
          {isEditing ? (
            <ShotEditor
              shot={shot}
              onSave={(updated) => {
                updateShot(plannerId, sceneId, shot.shotId, updated)
                setIsEditing(false)
              }}
              onCancel={() => setIsEditing(false)}
            />
          ) : (
            <div className="space-y-3 text-[12.5px]">
              {shot.regeneratedNote && (
                <div className="rounded-lg border border-[#10A37F]/30 bg-[#10A37F]/5 px-2.5 py-1.5 text-[11px] text-[#0D8A6B]">
                  {shot.regeneratedNote}
                </div>
              )}

              {/* All 10 Required Production Fields */}
              <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    1. Shot ID
                  </span>
                  <p className="font-mono text-xs font-semibold text-[#212121]">{shot.shotId}</p>
                </div>

                <div>
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    2. Duration
                  </span>
                  <p className="text-[#212121]">{shot.durationSeconds} seconds</p>
                </div>

                <div>
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    3. Framing
                  </span>
                  <p className="text-[#212121]">{shot.framing}</p>
                </div>

                <div>
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    4. Camera Movement
                  </span>
                  <p className="text-[#212121]">{shot.cameraMovement}</p>
                </div>

                <div>
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    5. Characters
                  </span>
                  <p className="text-[#212121]">
                    {shot.characters.length > 0 ? shot.characters.join(', ') : 'None'}
                  </p>
                </div>

                <div>
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    6. Location
                  </span>
                  <p className="text-[#212121]">{shot.location}</p>
                </div>
              </div>

              <div className="rounded-lg border border-[#E5E7EB] bg-[#F9F9F9] p-2.5">
                <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                  7. What We See
                </span>
                <p className="mt-0.5 leading-relaxed text-[#212121]">{shot.whatWeSee}</p>
              </div>

              <div className="rounded-lg border border-[#E5E7EB] bg-[#F9F9F9] p-2.5">
                <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                  8. Dialogue (Speaker, Exact Line &amp; Delivery)
                </span>
                {shot.dialogue ? (
                  <div className="mt-1 space-y-0.5 text-[#212121]">
                    <p>
                      <span className="font-semibold">{shot.dialogue.speaker}:</span> &ldquo;
                      {shot.dialogue.line}&rdquo;
                    </p>
                    <p className="text-[11.5px] text-[#6B7280]">
                      Delivery: {shot.dialogue.delivery}
                    </p>
                  </div>
                ) : (
                  <p className="mt-0.5 italic text-[#6B7280]">No spoken dialogue (visual beat)</p>
                )}
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-[#E5E7EB] bg-[#F9F9F9] p-2.5">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    9. Emotion
                  </span>
                  <p className="mt-0.5 text-[#212121]">{shot.emotion}</p>
                </div>
                <div className="rounded-lg border border-[#E5E7EB] bg-[#F9F9F9] p-2.5">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
                    10. Sound
                  </span>
                  <p className="mt-0.5 text-[#212121]">{shot.sound}</p>
                </div>
              </div>

              {/* Action Controls */}
              <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setShowRegen((prev) => !prev)
                    setIsEditing(false)
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-2.5 py-1.5 text-xs font-medium text-[#212121] transition-colors hover:bg-[#F1F1F1]"
                >
                  <RefreshCw className="h-3 w-3 text-[#10A37F]" />
                  Regenerate shot
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsEditing(true)
                    setShowRegen(false)
                  }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-2.5 py-1.5 text-xs font-medium text-[#212121] transition-colors hover:bg-[#F1F1F1]"
                >
                  <Pencil className="h-3 w-3 text-[#6B7280]" />
                  Edit shot
                </button>
              </div>

              {showRegen && (
                <ShotRegenerateBox
                  shotId={shot.shotId}
                  isRegenerating={isRegenerating}
                  onRegenerate={handleRegenerate}
                  onClose={() => setShowRegen(false)}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
