import type { ShotPlanner } from './planner'
import type { StoryDraftState, StoryImprovementSuggestion } from './story'

export type MessageRole = 'user' | 'assistant'

export interface UploadedAttachment {
  id: string
  name: string
  size: number
  type: 'pdf' | 'txt' | 'docx'
  previewText?: string
}

export interface OptionChoice {
  id: string
  label: string
  action?: 'send' | 'focus_input'
  value?: string
}

export type InterviewStep =
  | 'idle'
  | 'relationship'
  | 'suggestions'
  | 'visual_style'
  | 'mood_emotion'
  | 'camera_ending'
  | 'ready_for_plan'
  | 'planned'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  createdAt: number
  attachment?: UploadedAttachment
  options?: OptionChoice[]
  selectedOptionId?: string
  suggestions?: StoryImprovementSuggestion[]
  plannerId?: string
  plannerSnapshot?: ShotPlanner
  isApprovalCard?: boolean
}

export interface Conversation {
  id: string
  title: string
  projectId: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
  storyDraft: StoryDraftState
  interviewStep: InterviewStep
  plannerId?: string
}

export interface StoryProject {
  id: string
  name: string
  description: string
}
