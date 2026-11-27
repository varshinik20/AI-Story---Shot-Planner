import { cn } from '@/lib/utils'

export function StoryForgeLogo({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 28 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('shrink-0', className)}
      aria-label="StoryForge logo"
    >
      <rect x="2" y="2" width="24" height="24" rx="7" fill="#212121" />
      <path
        d="M8.5 9.5H19.5M8.5 14H15.5M8.5 18.5H13"
        stroke="#FFFFFF"
        strokeWidth="1.9"
        strokeLinecap="round"
      />
      <circle cx="18.5" cy="17.5" r="2.5" fill="#10A37F" />
    </svg>
  )
}
