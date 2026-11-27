import { CheckCircle2, Download, Pencil } from 'lucide-react'
import type { ShotPlanner } from '@/types/planner'
import { useProjectStore } from '@/store/projectStore'
import { exportShotPlannerToPdf } from '@/lib/pdfExport'
import { formatDuration } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface ApprovalPanelProps {
  planner: ShotPlanner
  onRequestEdit: () => void
}

export function ApprovalPanel({ planner, onRequestEdit }: ApprovalPanelProps) {
  const { approvePlanner, unapprovePlanner } = useProjectStore()

  const handleExport = () => {
    exportShotPlannerToPdf(planner)
  }

  return (
    <div className="rounded-2xl border border-[#E5E7EB] bg-[#F9F9F9] p-4 sm:p-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[#6B7280]">
            Production Summary
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#212121]">
            <span>
              <strong>{planner.overview.totalScenes}</strong> Scenes
            </span>
            <span>
              <strong>{planner.overview.totalShots}</strong> Shots
            </span>
            <span>
              <strong>{planner.overview.dialogueLines}</strong> Dialogue lines
            </span>
            <span>
              <strong>{formatDuration(planner.overview.runningTimeSeconds)}</strong> Total runtime
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!planner.isApproved ? (
            <>
              <Button type="button" variant="outline" size="sm" onClick={onRequestEdit}>
                <Pencil className="h-3.5 w-3.5" />
                Edit Shot Planner
              </Button>
              <Button
                type="button"
                variant="accent"
                size="sm"
                onClick={() => approvePlanner(planner.id)}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Approve Shot Planner
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => unapprovePlanner(planner.id)}
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit Shot Planner
              </Button>
              <Button type="button" variant="accent" size="sm" onClick={handleExport}>
                <Download className="h-3.5 w-3.5" />
                Export PDF
              </Button>
            </>
          )}
        </div>
      </div>

      {planner.isApproved ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#10A37F]/30 bg-[#10A37F]/10 px-3.5 py-2.5 text-xs text-[#0D8A6B]">
          <span className="flex items-center gap-2 font-medium">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Shot Planner approved! Your production breakdown is ready for export.
          </span>
          <button
            type="button"
            onClick={handleExport}
            className="font-semibold underline hover:no-underline"
          >
            Download PDF
          </button>
        </div>
      ) : (
        <div className="mt-3 flex items-center justify-between border-t border-[#E5E7EB] pt-2.5 text-[11.5px] text-[#6B7280]">
          <span>Review and edit any shot above, or export a draft PDF anytime.</span>
          <button
            type="button"
            onClick={handleExport}
            className="inline-flex items-center gap-1 font-medium text-[#212121] hover:text-[#10A37F]"
          >
            <Download className="h-3 w-3" />
            Export Draft PDF
          </button>
        </div>
      )}
    </div>
  )
}
