import { motion } from 'framer-motion'
import { StoryForgeLogo } from './StoryForgeLogo'

export function LoadingIndicator({ label = 'StoryForge is thinking...' }: { label?: string }) {
  return (
    <div className="flex items-start gap-3.5 py-2">
      <StoryForgeLogo className="mt-0.5 h-7 w-7" />
      <div className="flex items-center gap-2 pt-1.5 text-sm text-[#6B7280]">
        <div className="flex items-center gap-1">
          {[0, 1, 2].map((idx) => (
            <motion.span
              key={idx}
              className="h-1.5 w-1.5 rounded-full bg-[#10A37F]"
              animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
              transition={{
                duration: 0.9,
                repeat: Infinity,
                delay: idx * 0.16,
                ease: 'easeInOut',
              }}
            />
          ))}
        </div>
        <span>{label}</span>
      </div>
    </div>
  )
}
