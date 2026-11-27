import { cn } from '@/lib/utils'

export const STYLE_SUGGESTION_OPTIONS = [
  'Cinematic realism',
  'Hand-painted animation',
  'Anime',
  'Dark fantasy',
  'Documentary style',
  'Custom direction',
] as const

interface StyleSuggestionsProps {
  disabled?: boolean
  selectedStyle?: string | null
  onSelectStyle: (style: string) => void
  onCustomDirection: () => void
}

export function StyleSuggestions({
  disabled = false,
  selectedStyle,
  onSelectStyle,
  onCustomDirection,
}: StyleSuggestionsProps) {
  return (
    <div className="flex flex-wrap gap-2 pt-0.5" aria-label="Visual style suggestions">
      {STYLE_SUGGESTION_OPTIONS.map((style) => {
        const isCustom = style === 'Custom direction'
        const isSelected =
          !isCustom &&
          Boolean(selectedStyle) &&
          selectedStyle?.toLowerCase() === style.toLowerCase()

        return (
          <button
            key={style}
            type="button"
            disabled={disabled && !isCustom}
            onClick={() => {
              if (isCustom) {
                onCustomDirection()
              } else {
                onSelectStyle(style)
              }
            }}
            className={cn(
              'rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition-colors',
              isSelected
                ? 'border-[#10A37F] bg-[#10A37F]/10 text-[#0D8A6B]'
                : disabled && !isCustom
                ? 'border-[#E5E7EB] bg-[#F9F9F9] text-[#9CA3AF] cursor-default'
                : 'border-[#E5E7EB] bg-white text-[#212121] hover:border-[#10A37F] hover:bg-[#F9F9F9]'
            )}
          >
            {style}.
          </button>
        )
      })}
    </div>
  )
}
