/**
 * CINEMIND API client — talks to the FastAPI backend.
 */

import type { InterviewStep, OptionChoice } from '@/types/chat'
import type { ShotPlanner } from '@/types/planner'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export interface AIChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AIChatRequest {
  messages: AIChatMessage[]
  interview_step: InterviewStep
  story_draft: Record<string, unknown>
}

export interface AIChatResponse {
  content: string
  next_step: InterviewStep
  options: OptionChoice[] | null
  planner: ShotPlanner | null
  suggested_title: string | null
}

export async function sendAIChat(payload: AIChatRequest): Promise<AIChatResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/ai/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`AI chat failed (${res.status}): ${err}`)
  }

  return res.json() as Promise<AIChatResponse>
}

