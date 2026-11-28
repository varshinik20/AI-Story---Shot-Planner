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
  intake_state?: {
    story_title: string | null
    visual_style: string | null
    story_context: string | null
    status: string
    confirmed: boolean
  }
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

export async function extractDocumentText(file: File): Promise<string> {
  const buffer = await file.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 0x8000
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  const content_base64 = btoa(binary)

  const res = await fetch(`${BASE_URL}/api/v1/ai/extract-document`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: file.name, content_base64 }),
  })

  if (!res.ok) {
    return ''
  }
  const data = (await res.json()) as { text?: string }
  return data.text?.trim() ?? ''
}

