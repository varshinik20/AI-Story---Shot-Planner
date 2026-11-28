import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Shot, ShotPlanner } from '@/types/planner'
import { BOY_WHO_CRIED_WOLF_PLANNER } from '@/data/boyWhoCriedWolf'
import { simulateShotRegeneration } from '@/lib/mockAi'

interface ProjectState {
  planners: Record<string, ShotPlanner>
  defaultVideoFormat: string
  defaultFrameRate: string
  registerPlanner: (planner: ShotPlanner) => void
  updateShot: (plannerId: string, sceneId: string, shotId: string, updatedShot: Shot) => void
  regenerateShot: (plannerId: string, sceneId: string, shotId: string, feedback: string) => void
  approvePlanner: (plannerId: string) => void
  unapprovePlanner: (plannerId: string) => void
  setDefaults: (format: string, fps: string) => void
  resetPlanners: () => void
}

function clampShotDuration(shot: Shot): Shot {
  const raw = Number(shot.durationSeconds) || 4
  const hasDialogue = Boolean(shot.dialogue?.line?.trim())
  const emotionText = `${shot.emotion || ''} ${shot.dialogue?.delivery || ''}`.toLowerCase()
  const highEmotion =
    /\b(deep|intense|heartfelt|tearful|emotional|desperate|triumphant|climactic|anguish|grief|sorrow|joy|relief|pleading|passionate|trembling|crying|determined|courage|moral|hope|love|fear|awe|proud|broken|devastated|revelation)\b/.test(
      emotionText
    )
  const maxAllowed = hasDialogue && highEmotion ? 7 : 5
  const clamped = Math.min(Math.max(Math.round(raw), 1), maxAllowed)
  return clamped === shot.durationSeconds ? shot : { ...shot, durationSeconds: clamped }
}

function recalculateOverview(planner: ShotPlanner): ShotPlanner {
  let totalShots = 0
  let dialogueLines = 0
  let runningTimeSeconds = 0

  const normalizedScenes = planner.scenes.map((scene) => {
    const normalizedShots = scene.shots.map((rawShot) => {
      const shot = clampShotDuration(rawShot)
      totalShots += 1
      runningTimeSeconds += shot.durationSeconds
      if (shot.dialogue && shot.dialogue.line.trim().length > 0) {
        dialogueLines += 1
      }
      return shot
    })
    return { ...scene, shots: normalizedShots }
  })

  return {
    ...planner,
    scenes: normalizedScenes,
    overview: {
      ...planner.overview,
      totalScenes: normalizedScenes.length,
      totalShots,
      dialogueLines,
      runningTimeSeconds,
    },
  }
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set) => ({
      planners: {
        [BOY_WHO_CRIED_WOLF_PLANNER.id]: BOY_WHO_CRIED_WOLF_PLANNER,
      },
      defaultVideoFormat: '16:9 (1920x1080 HD)',
      defaultFrameRate: '24 fps',

      registerPlanner: (planner) =>
        set((state) => ({
          planners: {
            ...state.planners,
            [planner.id]: recalculateOverview(planner),
          },
        })),

      updateShot: (plannerId, sceneId, shotId, updatedShot) =>
        set((state) => {
          const existing = state.planners[plannerId]
          if (!existing) return state

          const updatedScenes = existing.scenes.map((scene) => {
            if (scene.sceneId !== sceneId) return scene
            return {
              ...scene,
              shots: scene.shots.map((shot) => (shot.shotId === shotId ? updatedShot : shot)),
            }
          })

          return {
            planners: {
              ...state.planners,
              [plannerId]: recalculateOverview({
                ...existing,
                scenes: updatedScenes,
              }),
            },
          }
        }),

      regenerateShot: (plannerId, sceneId, shotId, feedback) =>
        set((state) => {
          const existing = state.planners[plannerId]
          if (!existing) return state

          const updatedScenes = existing.scenes.map((scene) => {
            if (scene.sceneId !== sceneId) return scene
            return {
              ...scene,
              shots: scene.shots.map((shot) =>
                shot.shotId === shotId ? simulateShotRegeneration(shot, feedback) : shot
              ),
            }
          })

          return {
            planners: {
              ...state.planners,
              [plannerId]: recalculateOverview({
                ...existing,
                scenes: updatedScenes,
              }),
            },
          }
        }),

      approvePlanner: (plannerId) =>
        set((state) => {
          const existing = state.planners[plannerId]
          if (!existing) return state
          return {
            planners: {
              ...state.planners,
              [plannerId]: {
                ...existing,
                isApproved: true,
                approvedAt: Date.now(),
              },
            },
          }
        }),

      unapprovePlanner: (plannerId) =>
        set((state) => {
          const existing = state.planners[plannerId]
          if (!existing) return state
          return {
            planners: {
              ...state.planners,
              [plannerId]: {
                ...existing,
                isApproved: false,
              },
            },
          }
        }),

      setDefaults: (defaultVideoFormat, defaultFrameRate) =>
        set({ defaultVideoFormat, defaultFrameRate }),

      resetPlanners: () =>
        set({
          planners: {
            [BOY_WHO_CRIED_WOLF_PLANNER.id]: BOY_WHO_CRIED_WOLF_PLANNER,
          },
        }),
    }),
    {
      name: 'storyforge_planners_v1',
    }
  )
)
