import type { StoryIntakeState } from '../types/storyIntake.types'

const STORAGE_KEY = 'storyforge_intake_states_v1'

export interface StoryIntakePersistenceAdapter {
  loadAll(): Record<string, StoryIntakeState>
  get(conversationId: string): StoryIntakeState | null
  save(state: StoryIntakeState): void
  remove(conversationId: string): void
  clearAll(): void
}

function readMap(): Record<string, StoryIntakeState> {
  if (typeof window === 'undefined' || !window.localStorage) return {}
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object'
      ? (parsed as Record<string, StoryIntakeState>)
      : {}
  } catch {
    return {}
  }
}

function writeMap(map: Record<string, StoryIntakeState>): void {
  if (typeof window === 'undefined' || !window.localStorage) return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
  } catch {
    // Ignore quota errors in restricted storage environments
  }
}

export const storyIntakePersistence: StoryIntakePersistenceAdapter = {
  loadAll() {
    return readMap()
  },

  get(conversationId: string) {
    const map = readMap()
    return map[conversationId] ?? null
  },

  save(state: StoryIntakeState) {
    const map = readMap()
    map[state.conversationId] = state
    writeMap(map)
  },

  remove(conversationId: string) {
    const map = readMap()
    delete map[conversationId]
    writeMap(map)
  },

  clearAll() {
    if (typeof window === 'undefined' || !window.localStorage) return
    window.localStorage.removeItem(STORAGE_KEY)
  },
}
