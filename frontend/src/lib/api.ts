/**
 * CINEMIND API client — talks to the FastAPI backend across all workflow engines.
 */

import type { InterviewStep, OptionChoice } from '@/types/chat'
import type { ShotPlanner } from '@/types/planner'

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''

let inMemoryCsrfToken: string | null = null
let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

export function setCsrfToken(token: string | null): void {
  inMemoryCsrfToken = token
}

function readCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null
  const match = /(?:^|;\s*)storyforge_csrf=([^;]+)/.exec(document.cookie)
  return match ? decodeURIComponent(match[1]) : null
}

function getEffectiveCsrfToken(): string | null {
  return inMemoryCsrfToken ?? readCsrfCookie()
}

export class ApiError extends Error {
  status: number
  code?: string

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function parseErrorResponse(res: Response, fallbackPrefix: string): Promise<ApiError> {
  let message = `${fallbackPrefix} (${res.status})`
  let code: string | undefined
  try {
    const payload = (await res.json()) as {
      detail?: string | { message?: string; code?: string }
      error?: { message?: string; code?: string }
      message?: string
      code?: string
    }
    if (payload.error?.message) {
      message = payload.error.message
      code = payload.error.code
    } else if (typeof payload.detail === 'string') {
      message = payload.detail
    } else if (payload.detail?.message) {
      message = payload.detail.message
      code = payload.detail.code
    } else if (payload.message) {
      message = payload.message
      code = payload.code
    }
  } catch {
    const text = await res.text().catch(() => '')
    if (text) message = text
  }
  return new ApiError(message, res.status, code)
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const isMutating = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  const csrfToken = isMutating ? getEffectiveCsrfToken() : null

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      ...(init?.headers ?? {}),
    },
  })

  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/api/v1/auth/')) {
      unauthorizedHandler?.()
    }
    throw await parseErrorResponse(res, 'Request failed')
  }

  return (await res.json()) as T
}

export interface AuthSessionResponse {
  authenticated: boolean
  username: string | null
  csrf_token: string | null
  expires_at: string | null
}

export interface LoginResponse {
  authenticated: boolean
  username: string
  csrf_token: string
  expires_at: string
  message: string
}

export async function fetchAuthMeApi(): Promise<AuthSessionResponse> {
  const data = await requestJson<AuthSessionResponse>('/api/v1/auth/me')
  if (data.authenticated && data.csrf_token) {
    inMemoryCsrfToken = data.csrf_token
  } else if (!data.authenticated) {
    inMemoryCsrfToken = null
  }
  return data
}

export async function loginApi(username: string, password: string): Promise<LoginResponse> {
  const data = await requestJson<LoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  inMemoryCsrfToken = data.csrf_token
  return data
}

export async function logoutApi(): Promise<void> {
  try {
    await requestJson('/api/v1/auth/logout', { method: 'POST' })
  } finally {
    inMemoryCsrfToken = null
  }
}

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
  return requestJson<AIChatResponse>('/api/v1/ai/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
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

  const csrfToken = getEffectiveCsrfToken()
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/extract-document`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    },
    body: JSON.stringify({ filename: file.name, content_base64 }),
  })

  if (!res.ok) {
    if (res.status === 401) {
      unauthorizedHandler?.()
    }
    return ''
  }
  const data = (await res.json()) as { text?: string }
  return data.text?.trim() ?? ''
}

export interface BackendIntakeState {
  story_title: string | null
  title_confirmed: boolean
  visual_style: string | null
  story_context: string | null
  dialogue_source: string | null
  confirmed_by_creator: boolean
  awaiting_confirmation: boolean
  suggested_titles: string[]
  input_sources_seen: string[]
  extracted_from_filename: string | null
}

export interface UnifiedChatResponse {
  project_id: string
  conversation_id: string
  story_id?: string | null
  workflow_stage: string
  intent: string
  intake_state: BackendIntakeState
  missing_fields: string[]
  next_question_field: string | null
  ready_for_story_development: boolean
  needs_confirmation: boolean
  assistant_message: string
  suggested_titles: string[]
  style_options: string[]
  user_message_id: string
  assistant_message_id: string
}

export interface StoryUploadResponse {
  project_id: string
  conversation_id: string
  story_id: string
  filename: string
  file_type: string
  word_count: number
  page_count: number | null
  extracted_text: string
  workflow_stage: string
  intake_state: BackendIntakeState
  missing_fields: string[]
  needs_confirmation: boolean
  ready_for_story_development: boolean
  assistant_message: string
  style_options: string[]
}

export interface BackendStorySuggestion {
  id: string
  story_id: string
  section_title: string
  original_passage: string
  suggested_passage: string
  explanation: string
  status: 'pending' | 'accepted' | 'rejected'
}

export interface BackendStoryDetail {
  id: string
  project_id: string
  conversation_id: string | null
  title: string
  visual_style: string | null
  premise: string
  source_type: string
  original_content: string
  working_content: string
  approved_content: string | null
  status: string
  structure_json: Record<string, unknown> | null
  versions: Array<{
    id: string
    version_number: number
    label: string
    content: string
    is_approved: boolean
  }>
  suggestions: BackendStorySuggestion[]
}

export interface CreativeIntentResponse {
  project_id: string
  creative_intent: {
    id: string
    project_id: string
    visual_style: string | null
    overall_mood: string | null
    pacing: string | null
    lighting: string | null
    camera_preferences: string | null
    audience_experience: string | null
    ending_tone: string | null
    is_complete: boolean
  }
  missing_dimensions: string[]
  is_complete: boolean
  next_question: string | null
  quick_options: string[]
  target_dimension: string | null
}

export interface NarrativeAnalysisResponse {
  project_id: string
  characters: Array<{
    id: string
    character_code: string
    name: string
    role: string
    physical_appearance: string
    clothing: string | null
    personality: string
    voice_characteristics: string
    emotional_development: string | null
    uncertain_details: string[]
  }>
  locations: Array<{
    id: string
    location_code: string
    name: string
    description: string
    lighting_characteristics: string | null
    time_of_day: string | null
    visual_elements: string[]
  }>
  events: Array<{
    id: string
    event_id: string
    description: string
    characters: string[]
    location: string | null
    timeline_position: number
    narrative_role: string
    emotion: string
    intensity: number
  }>
  graph: {
    id: string
    nodes: Array<Record<string, unknown>>
    edges: Array<Record<string, unknown>>
    diagnostics: {
      node_count: number
      edge_count: number
      event_count: number
      connected_components_count: number
      abrupt_emotional_transitions: Array<{
        from_event: string
        to_event: string
        from_emotion: string
        to_emotion: string
        recommendation: string
      }>
      emotional_arc: Array<{
        event_id: string
        emotion: string
        intensity: number
        narrative_role: string
      }>
      recommended_scene_clusters: Array<{
        suggested_scene_order: number
        location: string
        event_ids: string[]
        dominant_emotion: string
        peak_intensity: number
        needs_pacing_bridge: boolean
      }>
      narrative_health: string
    }
    story_structure: Record<string, unknown>
  }
  reasoning_preview?: {
    peak_event_id: string
    decision: {
      summary_rationale: string
    }
  } | null
}

export interface BackendShot {
  id: string
  project_id: string
  scene_uuid: string
  shot_id: string
  shot_order: number
  duration_seconds: number
  framing: string
  camera: { angle: string; movement: string }
  characters: string[]
  location: string
  visual_description: string
  dialogue: Array<{ speaker: string; exact_line: string; delivery: string }>
  emotion: string
  sound: string
  reasoning?: {
    emotion_score: number
    narrative_score: number
    director_score: number
    continuity_score: number
    weighted_total: number
    validation_notes: string[]
  } | null
}

export interface BackendScene {
  id: string
  project_id: string
  scene_id: string
  scene_order: number
  title: string
  location: string
  time_of_day: string
  summary: string
  event_ids: string[]
  is_approved: boolean
  shots_generated: boolean
  shots: BackendShot[]
}

export interface ShotAlternativeItem {
  id: string
  shot_uuid: string
  label: string
  title: string
  treatment: Record<string, unknown>
  audience_experience_effect: string
  is_selected: boolean
}

export interface ValidationIssueItem {
  id: string
  category: string
  severity: string
  scene_id: string | null
  shot_id: string | null
  message: string
  suggested_fix: string | null
  resolved: boolean
}

export interface ValidationReportResponse {
  project_id: string
  issue_count: number
  unresolved_count: number
  issues: ValidationIssueItem[]
}

export interface ProjectUsageResponse {
  project_id: string
  total_calls: number
  successful_calls: number
  failed_calls: number
  total_input_tokens: number
  total_output_tokens: number
  total_estimated_cost_usd: number | null
  total_execution_time_ms: number
  by_engine: Record<
    string,
    {
      calls: number
      successful_calls: number
      input_tokens: number
      output_tokens: number
      estimated_cost_usd: number | null
      execution_time_ms: number
    }
  >
}

export async function sendChatTurn(payload: {
  message: string
  input_source: 'text' | 'voice' | 'document'
  project_id?: string
  conversation_id?: string
  story_title?: string
  visual_style?: string
}): Promise<UnifiedChatResponse> {
  return requestJson<UnifiedChatResponse>('/api/v1/chat/message', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function uploadStoryFile(
  file: File,
  opts?: { projectId?: string; conversationId?: string; storyTitle?: string; visualStyle?: string }
): Promise<StoryUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  if (opts?.projectId) form.append('project_id', opts.projectId)
  if (opts?.conversationId) form.append('conversation_id', opts.conversationId)
  if (opts?.storyTitle) form.append('story_title', opts.storyTitle)
  if (opts?.visualStyle) form.append('visual_style', opts.visualStyle)
  return requestJson<StoryUploadResponse>('/api/v1/stories/upload', {
    method: 'POST',
    body: form,
  })
}

export async function developStoryApi(payload: {
  project_id?: string
  story_id?: string
  instruction?: string
  preserve_original_text?: boolean
}): Promise<BackendStoryDetail> {
  return requestJson<BackendStoryDetail>('/api/v1/stories/develop', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function decideStorySuggestionApi(
  suggestionId: string,
  decision: 'accept' | 'reject',
  editedText?: string
): Promise<BackendStoryDetail> {
  return requestJson<BackendStoryDetail>(`/api/v1/stories/suggestions/${suggestionId}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, edited_text: editedText }),
  })
}

export async function approveStoryApi(
  storyId: string,
  editedContent?: string
): Promise<BackendStoryDetail> {
  return requestJson<BackendStoryDetail>('/api/v1/stories/approve', {
    method: 'POST',
    body: JSON.stringify({ story_id: storyId, edited_content: editedContent }),
  })
}

export async function interviewIntentApi(
  projectId: string,
  storyId?: string
): Promise<CreativeIntentResponse> {
  return requestJson<CreativeIntentResponse>('/api/v1/intent/interview', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, story_id: storyId }),
  })
}

export async function answerIntentApi(payload: {
  project_id: string
  answer?: string
  updates?: Record<string, string>
  confirm?: boolean
}): Promise<CreativeIntentResponse> {
  return requestJson<CreativeIntentResponse>('/api/v1/intent/answer', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function analyzeNarrativeApi(
  projectId: string,
  storyId?: string
): Promise<NarrativeAnalysisResponse> {
  return requestJson<NarrativeAnalysisResponse>('/api/v1/narrative/analyze', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, story_id: storyId, include_reasoning_preview: true }),
  })
}

export async function generateScenesApi(
  projectId: string,
  approveImmediately = false
): Promise<BackendScene[]> {
  return requestJson<BackendScene[]>('/api/v1/scenes/generate', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, approve_immediately: approveImmediately }),
  })
}

export async function approveScenesApi(
  projectId: string,
  sceneIds?: string[],
  approveAll = false
): Promise<BackendScene[]> {
  return requestJson<BackendScene[]>('/api/v1/scenes/approve', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, scene_ids: sceneIds, approve_all: approveAll }),
  })
}

export async function generateSceneShotsApi(sceneUuid: string): Promise<BackendScene> {
  return requestJson<BackendScene>('/api/v1/shots/generate', {
    method: 'POST',
    body: JSON.stringify({ scene_uuid: sceneUuid }),
  })
}

export async function updateShotApi(
  shotUuid: string,
  updates: Partial<{
    duration_seconds: number
    framing: string
    camera: { angle: string; movement: string }
    characters: string[]
    location: string
    visual_description: string
    dialogue: Array<{ speaker: string; exact_line: string; delivery: string }>
    emotion: string
    sound: string
  }>
): Promise<BackendShot> {
  return requestJson<BackendShot>(`/api/v1/shots/${shotUuid}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function generateShotAlternativesApi(
  shotUuid: string,
  creativePrompt?: string
): Promise<ShotAlternativeItem[]> {
  return requestJson<ShotAlternativeItem[]>(`/api/v1/shots/${shotUuid}/alternatives`, {
    method: 'POST',
    body: JSON.stringify({ creative_prompt: creativePrompt }),
  })
}

export async function applyShotAlternativeApi(
  shotUuid: string,
  altId: string
): Promise<{ applied_alternative_id: string; shot: BackendShot }> {
  return requestJson<{ applied_alternative_id: string; shot: BackendShot }>(
    `/api/v1/shots/${shotUuid}/alternatives/${altId}/apply`,
    { method: 'POST' }
  )
}

export async function runValidationApi(projectId: string): Promise<ValidationReportResponse> {
  return requestJson<ValidationReportResponse>('/api/v1/validation/run', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId }),
  })
}

export async function resolveValidationIssueApi(issueId: string): Promise<ValidationIssueItem> {
  return requestJson<ValidationIssueItem>(`/api/v1/validation/${issueId}/resolve`, {
    method: 'POST',
  })
}

export async function approvePlannerApi(
  projectId: string,
  notes?: string,
  allowPartial = false
): Promise<{
  project_id: string
  approved: boolean
  approved_at: string
  scene_count: number
  shot_count: number
  export_url: string
}> {
  return requestJson('/api/v1/planner/approve', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, notes, allow_partial: allowPartial }),
  })
}

export function getPlannerExportUrl(projectId: string): string {
  return `${API_BASE_URL}/api/v1/planner/export/${projectId}`
}

export async function validatePlannerPdfApi(projectId: string): Promise<{
  valid: boolean
  issues: string[]
  scene_count?: number
  shot_count?: number
  dialogue_lines_count?: number
  total_runtime_seconds?: number
  character_count?: number
  location_count?: number
}> {
  return requestJson(`/api/v1/planner/validate-pdf/${projectId}`)
}

export async function downloadPlannerPdfApi(projectId: string): Promise<string> {
  const res = await fetch(getPlannerExportUrl(projectId), {
    method: 'GET',
    credentials: 'include',
  })
  if (!res.ok) {
    if (res.status === 401) {
      unauthorizedHandler?.()
    }
    throw await parseErrorResponse(res, 'PDF export failed')
  }

  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^";]+)"?/i.exec(disposition)
  const filename = match?.[1] || `Shot-Planner_${projectId}.pdf`

  const blobUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(blobUrl)
  return filename
}

export async function getConversationStateApi(conversationId: string): Promise<{
  project_id: string
  conversation_id: string
  story_id: string | null
  title: string
  workflow_stage: string
  intake_state: BackendIntakeState
  messages: Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    input_source?: string
    created_at?: string | null
  }>
}> {
  return requestJson(`/api/v1/chat/conversations/${conversationId}`)
}

export async function getProjectUsageApi(projectId: string): Promise<ProjectUsageResponse> {
  return requestJson<ProjectUsageResponse>(`/api/v1/usage/${projectId}`)
}

export async function getPlannerWorkspaceApi(projectId: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`/api/v1/planner/${projectId}`)
}
