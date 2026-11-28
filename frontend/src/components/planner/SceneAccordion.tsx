import { useState } from 'react'
import { ChevronDown, ChevronRight, ImageIcon, MapPin, Sun } from 'lucide-react'
import type { Scene } from '@/types/planner'
import { ShotCard } from './ShotCard'

interface SceneAccordionProps {
  plannerId: string
  scene: Scene
  defaultExpanded?: boolean
}

export function SceneAccordion({
  plannerId,
  scene,
  defaultExpanded = true,
}: SceneAccordionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  const sceneDuration = scene.shots.reduce((sum, s) => sum + s.durationSeconds, 0)

  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-[#F9F9F9]/60">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full flex-wrap items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-[#F1F1F1]/70 sm:px-5"
      >
        <div className="flex items-center gap-2.5">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-[#6B7280]" />
          ) : (
            <ChevronRight className="h-4 w-4 text-[#6B7280]" />
          )}
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-[#212121] px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white">
                {scene.sceneId}
              </span>
              <h4 className="text-sm font-semibold text-[#212121]">{scene.sceneTitle}</h4>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-[11.5px] text-[#6B7280]">
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {scene.locations.join(', ')}
              </span>
              <span className="inline-flex items-center gap-1">
                <Sun className="h-3 w-3" />
                {scene.timeOfDay}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-[#6B7280]">
          <span className="rounded-md border border-[#E5E7EB] bg-white px-2 py-0.5 font-medium text-[#212121]">
            {scene.shots.length} shots
          </span>
          <span className="rounded-md border border-[#E5E7EB] bg-white px-2 py-0.5">
            {sceneDuration}s
          </span>
        </div>
      </button>

      {expanded && (
        <div className="space-y-2 border-t border-[#E5E7EB] p-3 sm:p-4">
          {scene.shots.map((shot, idx) => (
            <ShotCard
              key={shot.shotId}
              plannerId={plannerId}
              sceneId={scene.sceneId}
              shot={shot}
              defaultExpanded={scene.sceneId === 'S01' && idx === 0}
            />
          ))}

          {scene.referenceImageUrl && (
            <div className="mt-3 overflow-hidden rounded-xl border border-[#E5E7EB] bg-white">
              <div className="flex items-center gap-1.5 border-b border-[#E5E7EB] bg-[#F9F9F9] px-3 py-1.5 text-[11px] font-medium text-[#6B7280]">
                <ImageIcon className="h-3.5 w-3.5 text-[#10A37F]" />
                <span>Scene Reference Frame</span>
              </div>
              <img
                src={scene.referenceImageUrl}
                alt={`Reference frame for ${scene.sceneTitle}`}
                className="aspect-video w-full object-cover"
                loading="lazy"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
