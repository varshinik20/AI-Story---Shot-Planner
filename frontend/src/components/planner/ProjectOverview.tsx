import { Clock, Film, MessageSquareQuote, Clapperboard } from 'lucide-react'
import type { ProjectOverviewData } from '@/types/planner'
import { formatDuration } from '@/lib/utils'

interface ProjectOverviewProps {
  overview: ProjectOverviewData
}

export function ProjectOverview({ overview }: ProjectOverviewProps) {
  const stats = [
    { label: 'Total Scenes', value: String(overview.totalScenes), icon: Clapperboard },
    { label: 'Total Shots', value: String(overview.totalShots), icon: Film },
    { label: 'Dialogue Lines', value: String(overview.dialogueLines), icon: MessageSquareQuote },
    { label: 'Running Time', value: formatDuration(overview.runningTimeSeconds), icon: Clock },
  ]

  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2 border-b border-[#E5E7EB] pb-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[#10A37F]">
            Project Overview
          </div>
          <h3 className="mt-0.5 text-lg font-semibold text-[#212121]">{overview.filmTitle}</h3>
        </div>
        <div className="flex flex-wrap gap-1.5 text-xs text-[#6B7280]">
          <span className="rounded-md border border-[#E5E7EB] bg-[#F9F9F9] px-2 py-1">
            {overview.videoFormat}
          </span>
          <span className="rounded-md border border-[#E5E7EB] bg-[#F9F9F9] px-2 py-1">
            {overview.frameRate}
          </span>
        </div>
      </div>

      <p className="text-[13.5px] leading-relaxed text-[#212121]">
        <span className="font-medium text-[#6B7280]">Logline: </span>
        {overview.logline}
      </p>

      <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {stats.map((item) => {
          const Icon = item.icon
          return (
            <div
              key={item.label}
              className="rounded-xl border border-[#E5E7EB] bg-[#F9F9F9] px-3 py-2.5"
            >
              <div className="flex items-center gap-1.5 text-[11px] text-[#6B7280]">
                <Icon className="h-3.5 w-3.5 text-[#10A37F]" />
                <span>{item.label}</span>
              </div>
              <div className="mt-1 text-sm font-semibold text-[#212121]">{item.value}</div>
            </div>
          )
        })}
      </div>

      <div className="mt-4 rounded-xl border border-[#E5E7EB] bg-[#F9F9F9] px-3.5 py-2.5">
        <div className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
          Creator&apos;s Intent
        </div>
        <p className="mt-1 text-[13px] leading-relaxed text-[#212121]">
          {overview.creatorsIntent}
        </p>
      </div>
    </div>
  )
}
