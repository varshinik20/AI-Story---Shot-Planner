export type SuggestionStatus = 'pending' | 'accepted' | 'rejected'

export interface StoryImprovementSuggestion {
  id: string
  sectionTitle: string
  originalSegment: string
  suggestedImprovement: string
  explanation: string
  status: SuggestionStatus
}

export interface StoryDraftState {
  title: string
  premise: string
  segments: string[]
  visualStyle?: string
  mood?: string
  cameraPreference?: string
  endingIntention?: string
  shadowMotive?: string
}
