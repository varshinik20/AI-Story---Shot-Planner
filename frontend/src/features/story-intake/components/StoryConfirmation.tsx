import { useState } from 'react'
import { Check, CheckCircle2, Pencil } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { IntakeFieldKey, StoryIntakeState } from '../types/storyIntake.types'

interface StoryConfirmationProps {
  intake: StoryIntakeState
  decision?: 'confirmed' | 'editing'
  disabled?: boolean
  onConfirm: () => void
  onEdit: (field?: IntakeFieldKey) => void
}

export function StoryConfirmation({
  intake,
  decision,
  disabled = false,
  onConfirm,
  onEdit,
}: StoryConfirmationProps) {
  const [showFieldPicker, setShowFieldPicker] = useState(false)

  const isConfirmed =
    decision === 'confirmed' ||
    intake.status === 'ready_for_generation' ||
    intake.status === 'completed'

  const isEditing = decision === 'editing'

  return (
    <div
      className={cn(
        'rounded-2xl border bg-[#F9F9F9] p-4 text-[13px]',
        isConfirmed ? 'border-[#10A37F]/40 bg-[#10A37F]/[0.03]' : 'border-[#E5E7EB]'
      )}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] pb-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#6B7280]">
          Story Intake Summary
        </span>
        {isConfirmed && (
          <span className="inline-flex items-center gap-1 rounded-full bg-[#10A37F]/15 px-2.5 py-0.5 text-[11px] font-medium text-[#0D8A6B]">
            <CheckCircle2 className="h-3 w-3" />
            Confirmed
          </span>
        )}
      </div>

      <dl className="space-y-2 text-[#212121]">
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
            Title
          </dt>
          <dd className="mt-0.5 font-medium">{intake.storyTitle.value ?? 'Not provided'}</dd>
        </div>

        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
            Visual Style
          </dt>
          <dd className="mt-0.5">{intake.visualStyle.value ?? 'Not provided'}</dd>
        </div>

        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
            Story Context
          </dt>
          <dd className="mt-0.5 leading-relaxed text-[#374151]">
            {intake.storyContext.value ?? 'Not provided'}
          </dd>
        </div>
      </dl>

      {!isConfirmed && !isEditing && (
        <div className="mt-4 space-y-2.5 border-t border-[#E5E7EB] pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={disabled}
              onClick={onConfirm}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#10A37F] px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#0D8A6B] disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" />
              Confirm and develop
            </button>

            <button
              type="button"
              disabled={disabled}
              onClick={() => setShowFieldPicker((prev) => !prev)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-3.5 py-1.5 text-xs font-medium text-[#212121] transition-colors hover:bg-[#F1F1F1] disabled:opacity-50"
            >
              <Pencil className="h-3.5 w-3.5 text-[#6B7280]" />
              Edit details
            </button>
          </div>

          {showFieldPicker && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[11px] text-[#6B7280]">Choose field to edit:</span>
              <button
                type="button"
                onClick={() => {
                  setShowFieldPicker(false)
                  onEdit('story_title')
                }}
                className="rounded-full border border-[#E5E7EB] bg-white px-2.5 py-1 text-[11.5px] font-medium text-[#212121] hover:border-[#10A37F]"
              >
                Edit Title
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowFieldPicker(false)
                  onEdit('visual_style')
                }}
                className="rounded-full border border-[#E5E7EB] bg-white px-2.5 py-1 text-[11.5px] font-medium text-[#212121] hover:border-[#10A37F]"
              >
                Edit Visual Style
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowFieldPicker(false)
                  onEdit('story_context')
                }}
                className="rounded-full border border-[#E5E7EB] bg-white px-2.5 py-1 text-[11.5px] font-medium text-[#212121] hover:border-[#10A37F]"
              >
                Edit Story Context
              </button>
            </div>
          )}
        </div>
      )}

      {isEditing && !isConfirmed && (
        <div className="mt-3 border-t border-[#E5E7EB] pt-2.5 text-xs text-[#6B7280]">
          Editing requested — reply below with the updated detail.
        </div>
      )}
    </div>
  )
}
