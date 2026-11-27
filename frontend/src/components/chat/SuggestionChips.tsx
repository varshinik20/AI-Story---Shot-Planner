import { Sparkles, Clapperboard, Compass } from 'lucide-react'

export interface WelcomeSuggestion {
  id: string
  label: string
  prompt: string
  icon: 'idea' | 'plan' | 'explore'
}

export const WELCOME_SUGGESTIONS: WelcomeSuggestion[] = [
  {
    id: 'sug_one_line',
    label: 'Develop a one-line story idea.',
    prompt: 'A girl discovers that her shadow has a life of its own.',
    icon: 'idea',
  },
  {
    id: 'sug_shot_plan',
    label: 'Transform a complete story into a shot plan.',
    prompt:
      'Transform this story into a complete scene-wise and shot-wise production plan: A lone lighthouse keeper on a storm-lashed cliff discovers a glowing message bottle washed ashore from a ship that vanished fifty years ago.',
    icon: 'plan',
  },
  {
    id: 'sug_explore',
    label: 'Explore characters, emotions and cinematic direction.',
    prompt:
      'A quiet botanist aboard an abandoned orbital greenhouse notices one extinct fern beginning to bloom toward Earth.',
    icon: 'explore',
  },
]

interface SuggestionChipsProps {
  onSelect: (prompt: string) => void
}

export function SuggestionChips({ onSelect }: SuggestionChipsProps) {
  const renderIcon = (icon: WelcomeSuggestion['icon']) => {
    switch (icon) {
      case 'idea':
        return <Sparkles className="h-4 w-4 text-[#10A37F]" />
      case 'plan':
        return <Clapperboard className="h-4 w-4 text-[#10A37F]" />
      case 'explore':
        return <Compass className="h-4 w-4 text-[#10A37F]" />
    }
  }

  return (
    <div className="mt-7 grid w-full max-w-2xl grid-cols-1 gap-2.5 sm:grid-cols-3">
      {WELCOME_SUGGESTIONS.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item.prompt)}
          className="group flex flex-col items-start gap-2.5 rounded-2xl border border-[#E5E7EB] bg-white p-4 text-left transition-colors hover:bg-[#F9F9F9] hover:border-[#D1D5DB]"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#F4F4F4] transition-colors group-hover:bg-white">
            {renderIcon(item.icon)}
          </div>
          <span className="text-[13px] font-medium leading-snug text-[#212121]">
            {item.label}
          </span>
        </button>
      ))}
    </div>
  )
}
