import { useState } from 'react'
import { Check, RefreshCw, X } from 'lucide-react'
import type { Shot } from '@/types/planner'
import { Button } from '@/components/ui/button'

interface ShotEditorProps {
  shot: Shot
  onSave: (updated: Shot) => void
  onCancel: () => void
}

const FRAMING_OPTIONS = [
  'Extreme Wide Shot (EWS)',
  'Wide Shot (WS)',
  'Medium Wide Shot (MWS)',
  'Medium Shot (MS)',
  'Medium Close-Up (MCU)',
  'Close-Up (CU)',
  'Extreme Close-Up (ECU)',
  'Over-the-Shoulder (OTS)',
  'Two-Shot',
  'Point of View (POV)',
]

const MOVEMENT_OPTIONS = [
  'Static',
  'Slow Pan Left',
  'Slow Pan Right',
  'Whip Pan',
  'Slow Push-In',
  'Pull-Back',
  'Tracking Shot',
  'Handheld Follow',
  'Tilt Up',
  'Tilt Down',
  'Crane Up',
  'Dolly Zoom',
]

export function ShotEditor({ shot, onSave, onCancel }: ShotEditorProps) {
  const [durationSeconds, setDurationSeconds] = useState(shot.durationSeconds)
  const [framing, setFraming] = useState(shot.framing)
  const [cameraMovement, setCameraMovement] = useState(shot.cameraMovement)
  const [charactersText, setCharactersText] = useState(shot.characters.join(', '))
  const [location, setLocation] = useState(shot.location)
  const [whatWeSee, setWhatWeSee] = useState(shot.whatWeSee)
  const [hasDialogue, setHasDialogue] = useState(Boolean(shot.dialogue))
  const [speaker, setSpeaker] = useState(shot.dialogue?.speaker || '')
  const [line, setLine] = useState(shot.dialogue?.line || '')
  const [delivery, setDelivery] = useState(shot.dialogue?.delivery || '')
  const [emotion, setEmotion] = useState(shot.emotion)
  const [sound, setSound] = useState(shot.sound)

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    const cleanedCharacters = charactersText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

    onSave({
      ...shot,
      durationSeconds: Math.max(1, Number(durationSeconds) || 1),
      framing,
      cameraMovement,
      characters: cleanedCharacters,
      location: location.trim() || shot.location,
      whatWeSee: whatWeSee.trim() || shot.whatWeSee,
      dialogue:
        hasDialogue && line.trim()
          ? {
              speaker: speaker.trim() || 'Character',
              line: line.trim(),
              delivery: delivery.trim() || 'Natural',
            }
          : null,
      emotion: emotion.trim() || shot.emotion,
      sound: sound.trim() || shot.sound,
    })
  }

  return (
    <form
      onSubmit={handleSave}
      className="space-y-3 rounded-xl border border-[#10A37F]/40 bg-[#F9F9F9] p-3.5 text-xs"
    >
      <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-2">
        <span className="font-semibold text-[#212121]">Editing {shot.shotId}</span>
        <button
          type="button"
          onClick={onCancel}
          className="rounded p-1 text-[#6B7280] hover:bg-[#E5E7EB] hover:text-[#212121]"
          aria-label="Cancel editing"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1 block font-medium text-[#6B7280]">Duration (seconds)</label>
          <input
            type="number"
            min={1}
            max={120}
            value={durationSeconds}
            onChange={(e) => setDurationSeconds(Number(e.target.value))}
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white px-2.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block font-medium text-[#6B7280]">Framing</label>
          <select
            value={framing}
            onChange={(e) => setFraming(e.target.value)}
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white px-2 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
          >
            {FRAMING_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block font-medium text-[#6B7280]">Camera Movement</label>
          <select
            value={cameraMovement}
            onChange={(e) => setCameraMovement(e.target.value)}
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white px-2 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
          >
            {MOVEMENT_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block font-medium text-[#6B7280]">
            Characters (comma-separated)
          </label>
          <input
            type="text"
            value={charactersText}
            onChange={(e) => setCharactersText(e.target.value)}
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white px-2.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block font-medium text-[#6B7280]">Location</label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white px-2.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block font-medium text-[#6B7280]">What We See</label>
        <textarea
          rows={2}
          value={whatWeSee}
          onChange={(e) => setWhatWeSee(e.target.value)}
          className="w-full rounded-lg border border-[#E5E7EB] bg-white p-2 text-xs leading-relaxed text-[#212121] focus:border-[#10A37F] focus:outline-none"
        />
      </div>

      {/* Dialogue Toggle & Fields */}
      <div className="rounded-lg border border-[#E5E7EB] bg-white p-2.5">
        <div className="flex items-center justify-between">
          <span className="font-medium text-[#212121]">Dialogue</span>
          <label className="inline-flex cursor-pointer items-center gap-1.5 text-[11px] text-[#6B7280]">
            <input
              type="checkbox"
              checked={hasDialogue}
              onChange={(e) => setHasDialogue(e.target.checked)}
              className="accent-[#10A37F]"
            />
            Include spoken line
          </label>
        </div>

        {hasDialogue && (
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
            <input
              type="text"
              placeholder="Speaker"
              value={speaker}
              onChange={(e) => setSpeaker(e.target.value)}
              className="h-8 rounded-lg border border-[#E5E7EB] px-2.5 text-xs focus:border-[#10A37F] focus:outline-none"
            />
            <input
              type="text"
              placeholder="Exact line"
              value={line}
              onChange={(e) => setLine(e.target.value)}
              className="h-8 rounded-lg border border-[#E5E7EB] px-2.5 text-xs sm:col-span-2 focus:border-[#10A37F] focus:outline-none"
            />
            <input
              type="text"
              placeholder="Delivery direction (e.g. breathless whisper)"
              value={delivery}
              onChange={(e) => setDelivery(e.target.value)}
              className="h-8 rounded-lg border border-[#E5E7EB] px-2.5 text-xs sm:col-span-3 focus:border-[#10A37F] focus:outline-none"
            />
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block font-medium text-[#6B7280]">Emotion</label>
          <input
            type="text"
            value={emotion}
            onChange={(e) => setEmotion(e.target.value)}
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white px-2.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block font-medium text-[#6B7280]">Sound</label>
          <input
            type="text"
            value={sound}
            onChange={(e) => setSound(e.target.value)}
            className="h-8 w-full rounded-lg border border-[#E5E7EB] bg-white px-2.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
          />
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 pt-1">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="accent" size="sm">
          <Check className="h-3.5 w-3.5" />
          Save Shot
        </Button>
      </div>
    </form>
  )
}

interface ShotRegenerateBoxProps {
  shotId: string
  isRegenerating: boolean
  onRegenerate: (feedback: string) => void
  onClose: () => void
}

export function ShotRegenerateBox({
  shotId,
  isRegenerating,
  onRegenerate,
  onClose,
}: ShotRegenerateBoxProps) {
  const [feedback, setFeedback] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!feedback.trim() || isRegenerating) return
    onRegenerate(feedback.trim())
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-2 flex flex-col gap-2 rounded-xl border border-[#E5E7EB] bg-[#F9F9F9] p-3 text-xs sm:flex-row sm:items-center"
    >
      <input
        type="text"
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder={`Feedback for ${shotId} (e.g. "Push in closer and heighten tension")`}
        className="h-8 flex-1 rounded-lg border border-[#E5E7EB] bg-white px-2.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
      />
      <div className="flex items-center gap-1.5">
        <Button
          type="submit"
          variant="accent"
          size="sm"
          disabled={!feedback.trim() || isRegenerating}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
          {isRegenerating ? 'Updating...' : 'Regenerate Shot'}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
