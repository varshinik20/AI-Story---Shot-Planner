import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Check,
  CheckCircle2,
  Download,
  Film,
  GitBranch,
  Loader2,
  MapPin,
  Pencil,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Users,
  Wand2,
  X,
} from 'lucide-react'
import {
  analyzeNarrativeApi,
  answerIntentApi,
  applyShotAlternativeApi,
  approvePlannerApi,
  approveScenesApi,
  approveStoryApi,
  decideStorySuggestionApi,
  developStoryApi,
  downloadPlannerPdfApi,
  generateSceneShotsApi,
  generateScenesApi,
  generateShotAlternativesApi,
  getPlannerWorkspaceApi,
  getProjectUsageApi,
  interviewIntentApi,
  regenerateSingleShotApi,
  resolveValidationIssueApi,
  runValidationApi,
  updateShotApi,
  updateStoryDetailsApi,
  type BackendScene,
  type BackendShot,
  type BackendStoryDetail,
  type CreativeIntentResponse,
  type NarrativeAnalysisResponse,
  type ProjectUsageResponse,
  type ShotAlternativeItem,
  type ValidationReportResponse,
} from '@/lib/api'
import { Button } from '@/components/ui/button'

interface WorkspaceSummary {
  scene_count: number
  shot_count: number
  dialogue_lines_count: number
  total_runtime_seconds: number
  character_count: number
  location_count: number
  production_format: string
}

interface WorkspaceCharacter {
  id: string
  character_code: string
  name: string
  role: string
  age_range?: string | null
  physical_appearance: string
  clothing?: string | null
  personality: string
  voice_characteristics: string
}

interface WorkspaceLocation {
  id: string
  location_code: string
  name: string
  description: string
  environment?: string | null
  lighting_characteristics?: string | null
  time_of_day?: string | null
  visual_elements: string[]
}

interface CinemindWorkflowPanelProps {
  projectId: string
  storyId?: string
  workflowStage?: string
}

export function CinemindWorkflowPanel({
  projectId,
  storyId,
  workflowStage,
}: CinemindWorkflowPanelProps) {
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [story, setStory] = useState<(BackendStoryDetail & { genre?: string; logline?: string; central_theme?: string }) | null>(null)
  const [summary, setSummary] = useState<WorkspaceSummary | null>(null)
  const [characters, setCharacters] = useState<WorkspaceCharacter[]>([])
  const [locations, setLocations] = useState<WorkspaceLocation[]>([])
  const [editingStory, setEditingStory] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftGenre, setDraftGenre] = useState('')
  const [draftStyle, setDraftStyle] = useState('')
  const [draftStoryText, setDraftStoryText] = useState('')
  const [intentState, setIntentState] = useState<CreativeIntentResponse | null>(null)
  const [narrative, setNarrative] = useState<NarrativeAnalysisResponse | null>(null)
  const [scenes, setScenes] = useState<BackendScene[]>([])
  const [validation, setValidation] = useState<ValidationReportResponse | null>(null)
  const [alternativesByShot, setAlternativesByShot] = useState<Record<string, ShotAlternativeItem[]>>({})
  const [editingShotId, setEditingShotId] = useState<string | null>(null)
  const [editShotFraming, setEditShotFraming] = useState('')
  const [editShotDuration, setEditShotDuration] = useState(4)
  const [editShotVisual, setEditShotVisual] = useState('')
  const [plannerApproved, setPlannerApproved] = useState(false)
  const [usage, setUsage] = useState<ProjectUsageResponse | null>(null)
  const [showUsage, setShowUsage] = useState(false)

  const hydrateWorkspace = useCallback(async () => {
    try {
      const ws = await getPlannerWorkspaceApi(projectId)
      const s = ws.story as (BackendStoryDetail & { genre?: string; logline?: string; central_theme?: string }) | null
      if (s) {
        setStory(s)
        setDraftTitle(s.title || '')
        setDraftGenre(s.genre || '')
        setDraftStyle(s.visual_style || '')
        setDraftStoryText(s.approved_content || s.working_content || '')
      }
      if (ws.summary) {
        setSummary(ws.summary as WorkspaceSummary)
      }
      if (Array.isArray(ws.characters)) {
        setCharacters(ws.characters as WorkspaceCharacter[])
      }
      if (Array.isArray(ws.locations)) {
        setLocations(ws.locations as WorkspaceLocation[])
      }
      if (ws.creative_intent) {
        const ci = ws.creative_intent as Record<string, unknown>
        setIntentState({
          project_id: projectId,
          creative_intent: {
            id: projectId,
            project_id: projectId,
            visual_style: (ci.visual_style as string) ?? null,
            overall_mood: (ci.overall_mood as string) ?? null,
            pacing: (ci.pacing as string) ?? null,
            lighting: (ci.lighting as string) ?? null,
            camera_preferences: (ci.camera_preferences as string) ?? null,
            audience_experience: (ci.audience_experience as string) ?? null,
            ending_tone: (ci.ending_tone as string) ?? null,
            is_complete: Boolean(ci.is_complete),
          },
          missing_dimensions: [],
          is_complete: Boolean(ci.is_complete),
          next_question: null,
          target_dimension: null,
          quick_options: [],
        })
      }
      if (Array.isArray(ws.scenes)) {
        setScenes(ws.scenes as BackendScene[])
      }
      setPlannerApproved(Boolean(ws.final_approved))
    } catch {
      // Hydrate silently if project is fresh
    }
  }, [projectId])

  useEffect(() => {
    void hydrateWorkspace()
  }, [hydrateWorkspace, workflowStage, storyId])

  const runAction = async (label: string, fn: () => Promise<void>) => {
    setBusyAction(label)
    setErrorMsg(null)
    try {
      await fn()
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Operation failed.')
    } finally {
      setBusyAction(null)
    }
  }

  const handleDevelopStory = () =>
    runAction('Develop Story', async () => {
      const res = await developStoryApi({
        project_id: projectId,
        story_id: story?.id ?? storyId,
      })
      setStory(res)
      setDraftStoryText(res.working_content)
    })

  const handleSuggestion = (suggId: string, decision: 'accept' | 'reject') =>
    runAction(`Suggestion (${decision})`, async () => {
      const res = await decideStorySuggestionApi(suggId, decision)
      setStory(res)
      setDraftStoryText(res.working_content)
    })

  const handleApproveStory = () =>
    runAction('Approve Story & Start Direction', async () => {
      if (!story) return
      const approved = await approveStoryApi(
        story.id,
        editingStory ? draftStoryText : undefined
      )
      setStory(approved)
      setEditingStory(false)
      const interview = await interviewIntentApi(projectId, approved.id)
      setIntentState(interview)
    })

  const handleQuickIntentAnswer = (dim: string, value: string) =>
    runAction('Update Direction', async () => {
      const updated = await answerIntentApi({
        project_id: projectId,
        updates: { [dim]: value },
        answer: `${dim.replace('_', ' ')}: ${value}`,
      })
      setIntentState(updated)
    })

  const handleAnalyzeNarrative = () =>
    runAction('Analyze Narrative & Emotion Graph', async () => {
      const res = await analyzeNarrativeApi(projectId, story?.id ?? storyId)
      setNarrative(res)
    })

  const handleGenerateScenes = () =>
    runAction('Propose Scenes', async () => {
      const res = await generateScenesApi(projectId, false)
      setScenes(res)
    })

  const handleApproveScene = (sceneUuid: string) =>
    runAction('Approve Scene', async () => {
      const res = await approveScenesApi(projectId, [sceneUuid], false)
      setScenes(res)
    })

  const handleGenerateSceneShots = (sceneUuid: string) =>
    runAction('Generate Scene Shots', async () => {
      const updatedScene = await generateSceneShotsApi(sceneUuid)
      setScenes((prev) => prev.map((sc) => (sc.id === updatedScene.id ? updatedScene : sc)))
    })

  const handleExploreWhatIf = (shotUuid: string) =>
    runAction('Explore What-If Treatments', async () => {
      const alts = await generateShotAlternativesApi(shotUuid)
      setAlternativesByShot((prev) => ({ ...prev, [shotUuid]: alts }))
    })

  const handleApplyAlt = (shotUuid: string, altId: string) =>
    runAction('Apply What-If Treatment', async () => {
      const res = await applyShotAlternativeApi(shotUuid, altId)
      setScenes((prev) =>
        prev.map((sc) => ({
          ...sc,
          shots: sc.shots.map((sh) => (sh.id === shotUuid ? res.shot : sh)),
        }))
      )
      setAlternativesByShot((prev) => ({
        ...prev,
        [shotUuid]: (prev[shotUuid] || []).map((a) => ({
          ...a,
          is_selected: a.id === altId,
        })),
      }))
    })

  const startEditShot = (sh: BackendShot) => {
    setEditingShotId(sh.id)
    setEditShotFraming(sh.framing)
    setEditShotDuration(sh.duration_seconds)
    setEditShotVisual(sh.visual_description)
  }

  const saveEditShot = (shotUuid: string) =>
    runAction('Save Shot Edit', async () => {
      const updated = await updateShotApi(shotUuid, {
        framing: editShotFraming,
        duration_seconds: Number(editShotDuration) || 4,
        visual_description: editShotVisual,
      })
      setScenes((prev) =>
        prev.map((sc) => ({
          ...sc,
          shots: sc.shots.map((sh) => (sh.id === shotUuid ? updated : sh)),
        }))
      )
      setEditingShotId(null)
    })

  const handleRunValidation = () =>
    runAction('Validate Continuity & Audience', async () => {
      const rep = await runValidationApi(projectId)
      setValidation(rep)
    })

  const handleApprovePlanner = () =>
    runAction('Approve Shot Planner', async () => {
      await approvePlannerApi(projectId, 'Creator approved in CINEMIND workspace', false)
      setPlannerApproved(true)
    })

  const handleDownloadPdf = () =>
    runAction('Export Production Shot Planner PDF', async () => {
      await downloadPlannerPdfApi(projectId)
    })

  const handleSaveStoryUpdates = (rebuildPlanner: boolean) =>
    runAction(rebuildPlanner ? 'Save Story & Rebuild Planner' : 'Save Story Updates', async () => {
      if (!story) return
      await updateStoryDetailsApi(story.id, {
        title: draftTitle,
        genre: draftGenre,
        visual_style: draftStyle,
        working_content: draftStoryText,
        rebuild_planner: rebuildPlanner,
      })
      setEditingStory(false)
      await hydrateWorkspace()
    })

  const handleRegenerateSingleShot = (shotUuid: string) =>
    runAction('Regenerate Shot', async () => {
      const updated = await regenerateSingleShotApi(shotUuid)
      setScenes((prev) =>
        prev.map((sc) => ({
          ...sc,
          shots: sc.shots.map((sh) => (sh.id === shotUuid ? updated : sh)),
        }))
      )
    })

  const handleToggleUsage = async () => {
    if (!showUsage) {
      await runAction('Fetch Usage Telemetry', async () => {
        const res = await getProjectUsageApi(projectId)
        setUsage(res)
      })
    }
    setShowUsage((p) => !p)
  }

  const totalShotsCount = scenes.reduce((acc, s) => acc + s.shots.length, 0)

  return (
    <div className="mt-4 space-y-4 rounded-2xl border border-[#E5E7EB] bg-[#F9FAFB] p-4 text-left">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] pb-3">
        <div className="flex items-center gap-2">
          <Film className="h-4 w-4 text-[#10A37F]" />
          <span className="text-xs font-semibold uppercase tracking-wider text-[#212121]">
            CINEMIND Production Studio
          </span>
          {workflowStage && (
            <span className="rounded-full bg-[#10A37F]/10 px-2.5 py-0.5 text-[11px] font-medium text-[#0D8A6B]">
              {workflowStage.replace(/_/g, ' ')}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" onClick={handleToggleUsage}>
            <Activity className="mr-1 h-3.5 w-3.5" />
            Usage & Cost
          </Button>
          {!story && (
            <Button
              type="button"
              size="sm"
              variant="accent"
              disabled={busyAction !== null}
              onClick={handleDevelopStory}
            >
              <Sparkles className="mr-1 h-3.5 w-3.5" />
              Develop Story Draft
            </Button>
          )}
        </div>
      </div>

      {busyAction && (
        <div className="flex items-center gap-2 rounded-xl border border-[#10A37F]/25 bg-white px-3 py-2 text-xs text-[#212121]">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-[#10A37F]" />
          <span>Running {busyAction}...</span>
        </div>
      )}

      {errorMsg && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {errorMsg}
        </div>
      )}

      {showUsage && usage && (
        <div className="rounded-xl border border-[#E5E7EB] bg-white p-3 text-xs">
          <div className="font-semibold text-[#212121]">Real LLM Usage Telemetry</div>
          <div className="mt-1 flex flex-wrap gap-4 text-[#4B5563]">
            <span>Calls: <strong>{usage.total_calls}</strong> ({usage.successful_calls} ok)</span>
            <span>Tokens: <strong>{usage.total_input_tokens} in / {usage.total_output_tokens} out</strong></span>
            <span>
              Est. Cost:{' '}
              <strong>
                {usage.total_estimated_cost_usd !== null
                  ? `$${usage.total_estimated_cost_usd.toFixed(5)}`
                  : 'N/A'}
              </strong>
            </span>
            <span>Latency: <strong>{usage.total_execution_time_ms} ms</strong></span>
          </div>
        </div>
      )}

      {/* Stage 1: Story Draft, Inline Suggestions & Approval */}
      {story && (
        <div className="space-y-3 rounded-xl border border-[#E5E7EB] bg-white p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-xs font-semibold text-[#212121]">
                1. Story Workspace — {story.title}
              </div>
              <div className="text-[11px] text-[#6B7280]">
                Status: {story.status} {story.approved_content ? '(Approved Snapshot Locked)' : '(Draft Working Copy)'}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busyAction !== null}
                onClick={handleDevelopStory}
              >
                <Sparkles className="mr-1 h-3 w-3" />
                {story.status === 'approved' ? 'Regenerate Story' : 'Develop Draft'}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setEditingStory((v) => !v)}
              >
                <Pencil className="mr-1 h-3 w-3" />
                {editingStory ? 'Cancel Edit' : 'Edit Story'}
              </Button>
              {story.status !== 'approved' && (
                <Button
                  type="button"
                  size="sm"
                  variant="accent"
                  disabled={busyAction !== null}
                  onClick={handleApproveStory}
                >
                  <CheckCircle2 className="mr-1 h-3 w-3" />
                  Approve Story
                </Button>
              )}
              {plannerApproved && (
                <Button
                  type="button"
                  size="sm"
                  variant="accent"
                  disabled={busyAction !== null}
                  onClick={handleDownloadPdf}
                >
                  <Download className="mr-1 h-3 w-3" />
                  Export PDF
                </Button>
              )}
            </div>
          </div>

          {summary && (
            <div className="flex flex-wrap gap-3 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] px-3 py-2 text-[11px] font-medium text-[#374151]">
              {story.genre && <span>Genre: <strong>{story.genre}</strong></span>}
              <span>Scenes: <strong>{summary.scene_count}</strong></span>
              <span>Shots: <strong>{summary.shot_count}</strong></span>
              <span>Dialogue Lines: <strong>{summary.dialogue_lines_count}</strong></span>
              <span>Runtime: <strong>{summary.total_runtime_seconds}s</strong></span>
              <span>Format: <strong>{summary.production_format}</strong></span>
            </div>
          )}

          {editingStory ? (
            <div className="space-y-2.5">
              <div className="grid gap-2 sm:grid-cols-3">
                <input
                  value={draftTitle}
                  onChange={(e) => setDraftTitle(e.target.value)}
                  placeholder="Story Title"
                  className="rounded-lg border border-[#D1D5DB] px-2.5 py-1.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
                />
                <input
                  value={draftGenre}
                  onChange={(e) => setDraftGenre(e.target.value)}
                  placeholder="Genre (e.g. Sci-Fi Drama)"
                  className="rounded-lg border border-[#D1D5DB] px-2.5 py-1.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
                />
                <input
                  value={draftStyle}
                  onChange={(e) => setDraftStyle(e.target.value)}
                  placeholder="Visual Style"
                  className="rounded-lg border border-[#D1D5DB] px-2.5 py-1.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
                />
              </div>
              <textarea
                value={draftStoryText}
                onChange={(e) => setDraftStoryText(e.target.value)}
                rows={6}
                className="w-full rounded-lg border border-[#D1D5DB] p-2.5 text-xs text-[#212121] focus:border-[#10A37F] focus:outline-none"
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busyAction !== null}
                  onClick={() => void handleSaveStoryUpdates(false)}
                >
                  Save Changes
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="accent"
                  disabled={busyAction !== null}
                  onClick={() => void handleSaveStoryUpdates(true)}
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  Save &amp; Rebuild Scenes/Shots
                </Button>
              </div>
            </div>
          ) : (
            <p className="whitespace-pre-wrap text-xs leading-relaxed text-[#374151]">
              {story.approved_content || story.working_content}
            </p>
          )}

          {(story.suggestions ?? []).filter((s) => s.status === 'pending').length > 0 && (
            <div className="space-y-2 border-t border-[#E5E7EB] pt-2.5">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#6B7280]">
                AI Suggestions (Accept or Reject)
              </div>
              {(story.suggestions ?? []).map((sg) => (
                <div key={sg.id} className="rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-2.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[#212121]">{sg.section_title}</span>
                    <span className="text-[11px] capitalize text-[#6B7280]">{sg.status}</span>
                  </div>
                  <p className="mt-1 text-[#4B5563]">“{sg.suggested_passage}”</p>
                  <p className="mt-0.5 text-[11px] text-[#6B7280]">{sg.explanation}</p>
                  {sg.status === 'pending' && (
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => handleSuggestion(sg.id, 'accept')}
                        className="inline-flex items-center gap-1 rounded bg-[#10A37F] px-2.5 py-1 text-[11px] font-medium text-white hover:bg-[#0D8A6B]"
                      >
                        <Check className="h-3 w-3" /> Accept
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSuggestion(sg.id, 'reject')}
                        className="inline-flex items-center gap-1 rounded border border-[#D1D5DB] bg-white px-2.5 py-1 text-[11px] font-medium text-[#374151]"
                      >
                        <X className="h-3 w-3" /> Reject
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Stage 2: Creative Direction */}
      {(intentState || story?.status === 'approved') && (
        <div className="space-y-2.5 rounded-xl border border-[#E5E7EB] bg-white p-3.5 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-[#212121]">2. Creative Direction & Audience Intent</span>
            {!intentState && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busyAction !== null}
                onClick={() =>
                  runAction('Start Intent Interview', async () => {
                    setIntentState(await interviewIntentApi(projectId, story?.id))
                  })
                }
              >
                Start Direction Interview
              </Button>
            )}
          </div>

          {intentState && (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {[
                  ['overall_mood', 'Mood'],
                  ['pacing', 'Pacing'],
                  ['lighting', 'Lighting'],
                  ['camera_preferences', 'Camera'],
                  ['audience_experience', 'Audience'],
                  ['ending_tone', 'Ending Tone'],
                ].map(([key, label]) => (
                  <div key={key} className="rounded border border-[#E5E7EB] px-2 py-1.5">
                    <div className="text-[10px] uppercase text-[#6B7280]">{label}</div>
                    <div className="font-medium text-[#212121]">
                      {(intentState.creative_intent as Record<string, unknown>)[key] as string || 'Pending'}
                    </div>
                  </div>
                ))}
              </div>

              {!intentState.is_complete && intentState.next_question && (
                <div className="rounded-lg bg-[#F4F4F5] p-2.5">
                  <p className="font-medium text-[#212121]">{intentState.next_question}</p>
                  {intentState.target_dimension && intentState.quick_options.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {intentState.quick_options.map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => handleQuickIntentAnswer(intentState.target_dimension!, opt)}
                          className="rounded-full border border-[#10A37F]/40 bg-white px-2.5 py-1 text-[11px] font-medium text-[#0D8A6B] hover:bg-[#10A37F]/10"
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {!narrative && (
                <Button
                  type="button"
                  size="sm"
                  variant="accent"
                  disabled={busyAction !== null}
                  onClick={handleAnalyzeNarrative}
                >
                  <GitBranch className="mr-1 h-3.5 w-3.5" />
                  Analyze Narrative & Emotion Graph
                </Button>
              )}
            </>
          )}
        </div>
      )}

      {/* Characters & Locations Profiles */}
      {(characters.length > 0 || locations.length > 0) && (
        <div className="grid gap-3 md:grid-cols-2">
          {characters.length > 0 && (
            <div className="space-y-2 rounded-xl border border-[#E5E7EB] bg-white p-3.5 text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-[#212121]">
                <Users className="h-3.5 w-3.5 text-[#10A37F]" />
                <span>Characters ({characters.length})</span>
              </div>
              <div className="space-y-2">
                {characters.map((ch) => (
                  <div key={ch.id} className="rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-2">
                    <div className="font-semibold text-[#212121]">
                      {ch.name} · <span className="font-normal text-[#6B7280]">{ch.role}{ch.age_range ? ` (${ch.age_range})` : ''}</span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-[#4B5563]">
                      {ch.physical_appearance}{ch.clothing ? ` Clothing: ${ch.clothing}` : ''}
                    </p>
                    <p className="mt-0.5 text-[11px] text-[#6B7280]">
                      {ch.personality} · Voice: {ch.voice_characteristics}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {locations.length > 0 && (
            <div className="space-y-2 rounded-xl border border-[#E5E7EB] bg-white p-3.5 text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-[#212121]">
                <MapPin className="h-3.5 w-3.5 text-[#10A37F]" />
                <span>Locations ({locations.length})</span>
              </div>
              <div className="space-y-2">
                {locations.map((loc) => (
                  <div key={loc.id} className="rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-2">
                    <div className="font-semibold text-[#212121]">
                      {loc.name}{loc.time_of_day ? ` · ${loc.time_of_day}` : ''}
                    </div>
                    <p className="mt-0.5 text-[11px] text-[#4B5563]">{loc.description}</p>
                    {(loc.environment || loc.lighting_characteristics) && (
                      <p className="mt-0.5 text-[11px] text-[#6B7280]">
                        {[loc.environment, loc.lighting_characteristics].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Stage 3: Story Intelligence + NetworkX Graph */}
      {narrative && (
        <div className="space-y-2.5 rounded-xl border border-[#E5E7EB] bg-white p-3.5 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-[#212121]">
              3. Story Intelligence & NetworkX Emotion Graph
            </span>
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">
              {narrative.graph.diagnostics.node_count} nodes · {narrative.graph.diagnostics.edge_count} edges ·{' '}
              {narrative.graph.diagnostics.narrative_health}
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            {narrative.graph.diagnostics.emotional_arc.map((pt) => (
              <div
                key={pt.event_id}
                className="rounded border border-[#E5E7EB] bg-[#F9FAFB] px-2 py-1 text-[11px]"
              >
                <span className="font-mono font-semibold">{pt.event_id}</span> · {pt.emotion} (
                {Math.round(pt.intensity * 100)}%)
              </div>
            ))}
          </div>

          {narrative.reasoning_preview && (
            <div className="rounded border border-[#10A37F]/30 bg-[#10A37F]/5 p-2 text-[11px] text-[#0D8A6B]">
              <strong>Cinematography Reasoning ({narrative.reasoning_preview.peak_event_id}):</strong>{' '}
              {narrative.reasoning_preview.decision.summary_rationale}
            </div>
          )}

          {scenes.length === 0 && (
            <Button
              type="button"
              size="sm"
              variant="accent"
              disabled={busyAction !== null}
              onClick={handleGenerateScenes}
            >
              Propose Scene Breakdown
            </Button>
          )}
        </div>
      )}

      {/* Stage 4: Progressive Scene-by-Scene Shot Generation & What-If */}
      {scenes.length > 0 && (
        <div className="space-y-3 rounded-xl border border-[#E5E7EB] bg-white p-3.5 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-[#212121]">
              4. Progressive Scene & Shot Production ({scenes.length} scenes · {totalShotsCount} shots)
            </span>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busyAction !== null}
                onClick={handleRunValidation}
              >
                <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                Run Validation
              </Button>
              {totalShotsCount > 0 && !plannerApproved && (
                <Button
                  type="button"
                  size="sm"
                  variant="accent"
                  disabled={busyAction !== null}
                  onClick={handleApprovePlanner}
                >
                  <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                  Approve Final Plan
                </Button>
              )}
              {plannerApproved && (
                <Button
                  type="button"
                  size="sm"
                  variant="accent"
                  disabled={busyAction !== null}
                  onClick={handleDownloadPdf}
                >
                  <Download className="mr-1 h-3.5 w-3.5" />
                  Download Production PDF
                </Button>
              )}
            </div>
          </div>

          {scenes.map((sc) => (
            <div key={sc.id} className="space-y-2 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="mr-2 rounded bg-[#212121] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white">
                    {sc.scene_id}
                  </span>
                  <span className="font-semibold text-[#212121]">{sc.title}</span>
                  <span className="ml-2 text-[11px] text-[#6B7280]">
                    {sc.location} · {sc.time_of_day}
                  </span>
                </div>
                <div className="flex gap-2">
                  {!sc.is_approved ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busyAction !== null}
                      onClick={() => handleApproveScene(sc.id)}
                    >
                      Approve Scene
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="accent"
                      disabled={busyAction !== null}
                      onClick={() => handleGenerateSceneShots(sc.id)}
                    >
                      {sc.shots_generated ? 'Regenerate Scene Shots' : 'Generate Shots for Scene'}
                    </Button>
                  )}
                </div>
              </div>
              <p className="text-[11.5px] text-[#4B5563]">{sc.summary}</p>

              {sc.shots.map((sh) => (
                <div key={sh.id} className="space-y-1.5 rounded-lg border border-[#E5E7EB] bg-white p-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold">
                        {sh.shot_id}
                      </span>
                      <span className="font-medium text-[#212121]">
                        {sh.framing} · {sh.camera?.angle} / {sh.camera?.movement}
                      </span>
                      <span className="text-[11px] text-[#6B7280]">{sh.duration_seconds}s · {sh.emotion}</span>
                    </div>
                    <div className="flex gap-1.5">
                      <button
                        type="button"
                        onClick={() => startEditShot(sh)}
                        className="rounded border border-[#E5E7EB] px-2 py-0.5 text-[11px] hover:bg-slate-50"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        disabled={busyAction !== null}
                        onClick={() => void handleRegenerateSingleShot(sh.id)}
                        className="inline-flex items-center gap-1 rounded border border-[#E5E7EB] px-2 py-0.5 text-[11px] hover:bg-slate-50"
                      >
                        <RefreshCw className="h-3 w-3" /> Regenerate Shot
                      </button>
                      <button
                        type="button"
                        onClick={() => handleExploreWhatIf(sh.id)}
                        className="inline-flex items-center gap-1 rounded border border-[#10A37F]/40 px-2 py-0.5 text-[11px] text-[#0D8A6B] hover:bg-[#10A37F]/10"
                      >
                        <Wand2 className="h-3 w-3" /> What-If
                      </button>
                    </div>
                  </div>

                  {editingShotId === sh.id ? (
                    <div className="space-y-2 border-t border-[#E5E7EB] pt-2">
                      <div className="flex gap-2">
                        <input
                          value={editShotFraming}
                          onChange={(e) => setEditShotFraming(e.target.value)}
                          className="flex-1 rounded border px-2 py-1 text-xs"
                          placeholder="Framing"
                        />
                        <input
                          type="number"
                          min={1}
                          value={editShotDuration}
                          onChange={(e) => setEditShotDuration(Number(e.target.value))}
                          className="w-20 rounded border px-2 py-1 text-xs"
                        />
                      </div>
                      <textarea
                        value={editShotVisual}
                        onChange={(e) => setEditShotVisual(e.target.value)}
                        rows={2}
                        className="w-full rounded border p-2 text-xs"
                      />
                      <div className="flex gap-2">
                        <Button type="button" size="sm" variant="accent" onClick={() => saveEditShot(sh.id)}>
                          Save
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => setEditingShotId(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="text-[11.5px] text-[#374151]">{sh.visual_description}</p>
                      <div className="text-[11px] text-[#6B7280]">
                        Sound: {sh.sound} · Dialogue:{' '}
                        {sh.dialogue.length > 0
                          ? sh.dialogue.map((d) => `${d.speaker}: "${d.exact_line}"`).join(' | ')
                          : 'None'}
                      </div>
                      {sh.reasoning && (
                        <div className="text-[10.5px] text-[#0D8A6B]">
                          Score: {sh.reasoning.weighted_total.toFixed(2)} (E={sh.reasoning.emotion_score}, N=
                          {sh.reasoning.narrative_score}, D={sh.reasoning.director_score}, C=
                          {sh.reasoning.continuity_score})
                        </div>
                      )}
                    </>
                  )}

                  {alternativesByShot[sh.id] && alternativesByShot[sh.id].length > 0 && (
                    <div className="mt-2 grid gap-2 border-t border-[#E5E7EB] pt-2 sm:grid-cols-3">
                      {alternativesByShot[sh.id].map((alt) => (
                        <div key={alt.id} className="rounded border border-[#E5E7EB] bg-[#F9FAFB] p-2 text-[11px]">
                          <div className="font-semibold text-[#212121]">
                            {alt.label}: {alt.title}
                          </div>
                          <p className="mt-1 text-[#4B5563]">{alt.audience_experience_effect}</p>
                          <button
                            type="button"
                            onClick={() => handleApplyAlt(sh.id, alt.id)}
                            className="mt-1.5 rounded bg-[#212121] px-2 py-0.5 text-[10.5px] font-medium text-white hover:bg-black"
                          >
                            {alt.is_selected ? 'Applied' : 'Apply Option'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Stage 5: Validation Issues */}
      {validation && (
        <div className="space-y-2 rounded-xl border border-[#E5E7EB] bg-white p-3.5 text-xs">
          <div className="font-semibold text-[#212121]">
            Continuity, Audience & Feasibility Report ({validation.unresolved_count} open)
          </div>
          {validation.issues.length === 0 ? (
            <div className="text-[#0D8A6B]">All checks passed cleanly with zero issues.</div>
          ) : (
            validation.issues.map((iss) => (
              <div
                key={iss.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded border border-amber-200 bg-amber-50/50 p-2"
              >
                <div>
                  <div className="flex items-center gap-1.5 font-medium text-[#212121]">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                    <span>
                      [{iss.category}] {iss.shot_id || iss.scene_id || 'Project'} — {iss.message}
                    </span>
                  </div>
                  {iss.suggested_fix && (
                    <div className="mt-0.5 text-[11px] text-[#4B5563]">Fix: {iss.suggested_fix}</div>
                  )}
                </div>
                {!iss.resolved && (
                  <button
                    type="button"
                    onClick={() =>
                      runAction('Resolve Issue', async () => {
                        const updated = await resolveValidationIssueApi(iss.id)
                        setValidation((prev) =>
                          prev
                            ? {
                                ...prev,
                                unresolved_count: Math.max(0, prev.unresolved_count - 1),
                                issues: prev.issues.map((x) => (x.id === iss.id ? updated : x)),
                              }
                            : prev
                        )
                      })
                    }
                    className="rounded border border-[#D1D5DB] bg-white px-2 py-0.5 text-[11px]"
                  >
                    Mark Resolved
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
