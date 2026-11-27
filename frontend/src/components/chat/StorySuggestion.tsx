import { Check, Sparkles, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StoryImprovementSuggestion, SuggestionStatus } from '@/types/story'

interface StorySuggestionProps {
  suggestion: StoryImprovementSuggestion
  onDecision: (suggestionId: string, status: SuggestionStatus) => void
}

export function StorySuggestion({ suggestion, onDecision }: StorySuggestionProps) {
  const isAccepted = suggestion.status === 'accepted'
  const isRejected = suggestion.status === 'rejected'
  const isPending = suggestion.status === 'pending'

  return (
    <div
      className={cn(
        'rounded-xl border bg-white p-4 transition-colors',
        isAccepted
          ? 'border-[#10A37F]/40 bg-[#10A37F]/[0.03]'
          : isRejected
          ? 'border-[#E5E7EB] bg-[#F9F9F9] opacity-80'
          : 'border-[#E5E7EB]'
      )}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-[#212121]">
          <Sparkles className="h-3.5 w-3.5 text-[#10A37F]" />
          <span>Story Suggestion: {suggestion.sectionTitle}</span>
        </div>

        {!isPending && (
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium',
              isAccepted
                ? 'bg-[#10A37F]/15 text-[#0D8A6B]'
                : 'bg-[#F1F1F1] text-[#6B7280]'
            )}
          >
            {isAccepted ? (
              <>
                <Check className="h-3 w-3" /> Accepted into story draft
              </>
            ) : (
              <>
                <X className="h-3 w-3" /> Kept original
              </>
            )}
          </span>
        )}
      </div>

      <div className="space-y-2.5 text-[13px]">
        <div className="rounded-lg border border-[#E5E7EB] bg-[#F9F9F9] px-3 py-2">
          <div className="mb-0.5 text-[11px] font-medium uppercase tracking-wide text-[#6B7280]">
            Original
          </div>
          <p className={cn('text-[#4B5563]', isAccepted && 'line-through opacity-70')}>
            {suggestion.originalSegment}
          </p>
        </div>

        <div className="rounded-lg border border-[#10A37F]/25 bg-white px-3 py-2">
          <div className="mb-0.5 text-[11px] font-medium uppercase tracking-wide text-[#10A37F]">
            Suggested Improvement
          </div>
          <p className="text-[#212121]">{suggestion.suggestedImprovement}</p>
        </div>

        <p className="text-xs leading-relaxed text-[#6B7280]">
          <span className="font-medium text-[#212121]">Why this helps: </span>
          {suggestion.explanation}
        </p>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          disabled={isAccepted}
          onClick={() => onDecision(suggestion.id, 'accepted')}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
            isAccepted
              ? 'bg-[#10A37F] text-white'
              : 'border border-[#E5E7EB] bg-white text-[#212121] hover:border-[#10A37F] hover:text-[#10A37F]'
          )}
        >
          <Check className="h-3.5 w-3.5" />
          {isAccepted ? 'Accepted' : 'Accept'}
        </button>

        <button
          type="button"
          disabled={isRejected}
          onClick={() => onDecision(suggestion.id, 'rejected')}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
            isRejected
              ? 'bg-[#E5E7EB] text-[#6B7280]'
              : 'border border-[#E5E7EB] bg-white text-[#6B7280] hover:bg-[#F1F1F1] hover:text-[#212121]'
          )}
        >
          <X className="h-3.5 w-3.5" />
          {isRejected ? 'Rejected' : 'Reject'}
        </button>
      </div>
    </div>
  )
}
