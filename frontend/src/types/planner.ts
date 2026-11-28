export type FramingOption =
  | 'Extreme Wide Shot (EWS)'
  | 'Wide Shot (WS)'
  | 'Medium Wide Shot (MWS)'
  | 'Medium Shot (MS)'
  | 'Medium Close-Up (MCU)'
  | 'Close-Up (CU)'
  | 'Extreme Close-Up (ECU)'
  | 'Over-the-Shoulder (OTS)'
  | 'Two-Shot'
  | 'Point of View (POV)'

export type CameraMovementOption =
  | 'Static'
  | 'Slow Pan Left'
  | 'Slow Pan Right'
  | 'Whip Pan'
  | 'Slow Push-In'
  | 'Pull-Back'
  | 'Tracking Shot'
  | 'Handheld Follow'
  | 'Tilt Up'
  | 'Tilt Down'
  | 'Crane Up'
  | 'Dolly Zoom'

export interface DialogueEntry {
  speaker: string
  line: string
  delivery: string
}

export interface Shot {
  shotId: string
  durationSeconds: number
  framing: FramingOption | string
  cameraMovement: CameraMovementOption | string
  characters: string[]
  location: string
  whatWeSee: string
  dialogue: DialogueEntry | null
  emotion: string
  sound: string
  regeneratedNote?: string
}

export interface Scene {
  sceneId: string
  sceneTitle: string
  locations: string[]
  timeOfDay: string
  shots: Shot[]
  referenceImageUrl?: string
  referenceImagePrompt?: string
  referenceImageError?: string
}

export interface CharacterProfile {
  id: string
  name: string
  role: string
  physicalAppearance: string
  personalityAndVoice: string
}

export interface LocationProfile {
  id: string
  name: string
  visualDescription: string
}

export interface ProjectOverviewData {
  filmTitle: string
  logline: string
  totalScenes: number
  totalShots: number
  dialogueLines: number
  runningTimeSeconds: number
  videoFormat: string
  frameRate: string
  creatorsIntent: string
}

export interface ShotPlanner {
  id: string
  overview: ProjectOverviewData
  characters: CharacterProfile[]
  locations: LocationProfile[]
  scenes: Scene[]
  isApproved: boolean
  approvedAt?: number
}
