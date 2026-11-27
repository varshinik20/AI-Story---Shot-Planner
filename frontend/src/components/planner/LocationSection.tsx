import { useState } from 'react'
import { ChevronDown, ChevronRight, MapPin } from 'lucide-react'
import type { LocationProfile } from '@/types/planner'

interface LocationSectionProps {
  locations: LocationProfile[]
}

export function LocationSection({ locations }: LocationSectionProps) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-[#F9F9F9] sm:px-5"
      >
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-[#10A37F]" />
          <span className="text-sm font-semibold text-[#212121]">
            Locations ({locations.length})
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
          {locations.map((loc) => (
            <div key={loc.id} className="px-4 py-3 sm:px-5">
              <h4 className="text-[13.5px] font-semibold text-[#212121]">{loc.name}</h4>
              <p className="mt-1 text-[12.5px] leading-relaxed text-[#4B5563]">
                {loc.visualDescription}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
