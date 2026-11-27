import { useState } from 'react'
import { ChevronDown, ChevronRight, Users } from 'lucide-react'
import type { CharacterProfile } from '@/types/planner'

interface CharacterSectionProps {
  characters: CharacterProfile[]
}

export function CharacterSection({ characters }: CharacterSectionProps) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-[#F9F9F9] sm:px-5"
      >
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-[#10A37F]" />
          <span className="text-sm font-semibold text-[#212121]">
            Characters ({characters.length})
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-[#6B7280]" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[#6B7280]" />
        )}
      </button>

      {expanded && (
        <div className="divide-y divide-[#E5E7EB] border-t border-[#E5E7EB]">
          {characters.map((char) => (
            <div key={char.id} className="px-4 py-3 sm:px-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="text-[13.5px] font-semibold text-[#212121]">{char.name}</h4>
                <span className="rounded-md bg-[#F4F4F4] px-2 py-0.5 text-[11px] font-medium text-[#6B7280]">
                  {char.role}
                </span>
              </div>
              <div className="mt-2 grid grid-cols-1 gap-2 text-[12.5px] leading-relaxed text-[#4B5563] sm:grid-cols-2">
                <div>
                  <span className="font-medium text-[#212121]">Physical appearance: </span>
                  {char.physicalAppearance}
                </div>
                <div>
                  <span className="font-medium text-[#212121]">Personality &amp; voice: </span>
                  {char.personalityAndVoice}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
