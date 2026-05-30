import { useEffect, useMemo, useState } from 'react'
import { createProject, getResult, getRun, getScenes, startRun, type ProjectResultOut, type SceneOut } from './lib/api'

type Step = 'input' | 'running' | 'preview' | 'result' | 'error'

function stageLabel(currentStage: string | null) {
  if (!currentStage) return 'Done'
  if (currentStage.includes('GENERATE_BLUEPRINT')) return 'Scripting'
  if (currentStage.includes('GENERATE_ASSETS')) return 'Generating assets'
  if (currentStage.includes('RENDER_ASSEMBLE')) return 'Rendering final'
  return currentStage
}

function pctFromRun(run: { current_stage: string | null; stage_runs: { stage: string; status: string }[] }) {
  const done = run.stage_runs.filter((s) => s.status === 'SUCCEEDED').length
  const total = Math.max(1, run.stage_runs.length || 3)
  const base = Math.round((done / total) * 100)
  const bump = run.current_stage ? 12 : 0
  return Math.min(99, Math.max(5, base + bump))
}

export default function AppReal() {
  const [step, setStep] = useState<Step>('input')
  const [idea, setIdea] = useState('')
  const [projectId, setProjectId] = useState<string | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [scenes, setScenes] = useState<SceneOut[]>([])
  const [runStatus, setRunStatus] = useState<string | null>(null)
  const [runStage, setRunStage] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<ProjectResultOut | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canGenerate = idea.trim().length >= 10

  const subtitlePreview = useMemo(() => {
    return scenes
      .map((s) => s.narration_script?.trim())
      .filter(Boolean)
      .slice(0, 3)
      .join(' ')
  }, [scenes])

  useEffect(() => {
    if (!projectId || !runId) return
    if (step !== 'running' && step !== 'preview') return

    let cancelled = false

    const tick = async () => {
      try {
        const run = await getRun(projectId, runId)
        if (cancelled) return
        setRunStatus(run.status)
        setRunStage(run.current_stage)
        setProgress(pctFromRun(run))

        const nextScenes = await getScenes(projectId)
        if (cancelled) return
        setScenes(nextScenes)
        if (nextScenes.length > 0 && step === 'running') setStep('preview')

        if (run.status === 'SUCCEEDED') {
          const r = await getResult(projectId)
          if (cancelled) return
          setResult(r)
          setProgress(100)
          setStep('result')
        }
        if (run.status === 'FAILED') {
          setError(run.error_message ?? 'Pipeline failed')
          setStep('error')
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e)
        setError(msg)
        setStep('error')
      }
    }

    void tick()
    const id = window.setInterval(() => void tick(), 2000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [projectId, runId, step])

  const onGenerate = async () => {
    try {
      setError(null)
      setProgress(0)
      setScenes([])
      setResult(null)
      const p = await createProject(idea.trim(), 60)
      setProjectId(p.id)
      const started = await startRun(p.id)
      setRunId(started.run.id)
      setRunStatus(started.run.status)
      setRunStage(started.run.current_stage)
      setStep('running')
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      setStep('error')
    }
  }

  const onReset = () => {
    setIdea('')
    setProjectId(null)
    setRunId(null)
    setScenes([])
    setRunStatus(null)
    setRunStage(null)
    setProgress(0)
    setResult(null)
    setError(null)
    setStep('input')
  }

  return (
    <div className="min-h-full bg-slate-950 text-slate-50">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8">
        <header className="flex items-center gap-3">
          <div className="text-base font-semibold tracking-tight">AI Storyteller</div>
          <div className="ml-auto text-xs text-slate-300">
            {projectId ? (
              <span className="rounded-full bg-white/5 px-3 py-1 ring-1 ring-white/10">Project {projectId.slice(0, 8)}</span>
            ) : (
              <span className="rounded-full bg-white/5 px-3 py-1 ring-1 ring-white/10">Ready</span>
            )}
          </div>
        </header>

        {step === 'input' && (
          <div className="rounded-3xl bg-white/[0.055] p-6 ring-1 ring-white/10">
            <div className="text-sm text-slate-300">Describe a story idea, then run the pipeline (FastAPI + Celery).</div>
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="Example: A girl searches for a lost memory in a rainy city..."
              spellCheck={false}
              className="mt-4 h-40 w-full resize-none rounded-2xl bg-slate-900/35 px-4 py-3 text-sm leading-6 text-slate-100 ring-1 ring-white/10 outline-none placeholder:text-slate-500 focus:ring-2 focus:ring-amber-200/35"
            />
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={!canGenerate}
                onClick={() => void onGenerate()}
                className="rounded-2xl bg-gradient-to-b from-amber-200/85 to-amber-200/55 px-5 py-2.5 text-sm font-semibold text-slate-950 ring-1 ring-amber-100/35 disabled:cursor-not-allowed disabled:from-amber-200/30 disabled:to-amber-200/20 disabled:text-slate-950/50"
              >
                Generate
              </button>
              <div className="text-xs text-slate-400">Minimum: 10 characters.</div>
            </div>
          </div>
        )}

        {(step === 'running' || step === 'preview') && (
          <div className="rounded-3xl bg-white/[0.055] p-6 ring-1 ring-white/10">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-lg font-semibold tracking-tight text-slate-100">{stageLabel(runStage)}</div>
                <div className="mt-1 text-sm text-slate-300">
                  Status: {runStatus ?? '—'} {runId ? `• Run ${runId.slice(0, 8)}` : ''}
                </div>
              </div>
              <button
                type="button"
                onClick={onReset}
                className="rounded-2xl bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 ring-1 ring-white/10 hover:bg-white/8"
              >
                New project
              </button>
            </div>

            <div className="mt-5">
              <div className="flex items-center justify-between text-xs text-slate-300">
                <div>Progress</div>
                <div>{progress}%</div>
              </div>
              <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-purple-300/90 via-amber-200/90 to-amber-100/90 transition-[width]"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {scenes.length > 0 && (
              <div className="mt-6 grid gap-4 lg:grid-cols-3">
                <div className="lg:col-span-2">
                  <div className="text-sm font-semibold tracking-tight text-slate-100">Storyboard</div>
                  <div className="mt-3 space-y-3">
                    {scenes.map((s) => (
                      <div key={s.id} className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-xs font-semibold text-slate-200">Scene {s.scene_number}</div>
                          <div className="text-[11px] text-slate-400">{s.status}</div>
                        </div>
                        <div className="mt-3 text-sm leading-6 text-slate-200">{s.narration_script}</div>
                        <div className="mt-3 text-xs leading-5 text-slate-400">{s.image_generation_prompt}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                  <div className="text-sm font-semibold tracking-tight text-slate-100">Subtitle preview</div>
                  <div className="mt-3 text-sm leading-6 text-slate-300">{subtitlePreview || '—'}</div>
                </div>
              </div>
            )}
          </div>
        )}

        {step === 'result' && (
          <div className="rounded-3xl bg-white/[0.055] p-6 ring-1 ring-white/10">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-lg font-semibold tracking-tight text-slate-100">Final video</div>
                <div className="mt-1 text-sm text-slate-300">{result?.mp4_url ? 'MP4 ready' : 'Waiting for output'}</div>
              </div>
              <button
                type="button"
                onClick={onReset}
                className="rounded-2xl bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 ring-1 ring-white/10 hover:bg-white/8"
              >
                New project
              </button>
            </div>
            <div className="mt-5 overflow-hidden rounded-3xl bg-black/30 ring-1 ring-white/10">
              {result?.mp4_url ? (
                <video className="h-full w-full" controls preload="metadata" src={result.mp4_url} />
              ) : (
                <div className="p-6 text-sm text-slate-300">No MP4 URL available yet.</div>
              )}
            </div>
            {(result?.mp4_url || result?.hls_master_url) && (
              <div className="mt-4 flex flex-wrap gap-3 text-xs">
                {result.mp4_url && (
                  <a className="rounded-full bg-white/5 px-3 py-1 ring-1 ring-white/10 hover:bg-white/8" href={result.mp4_url}>
                    Open MP4
                  </a>
                )}
                {result.hls_master_url && (
                  <a
                    className="rounded-full bg-white/5 px-3 py-1 ring-1 ring-white/10 hover:bg-white/8"
                    href={result.hls_master_url}
                  >
                    Open HLS
                  </a>
                )}
              </div>
            )}
          </div>
        )}

        {step === 'error' && (
          <div className="rounded-3xl bg-white/[0.055] p-6 ring-1 ring-white/10">
            <div className="text-lg font-semibold tracking-tight text-rose-200">Error</div>
            <div className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{error}</div>
            <div className="mt-4">
              <button
                type="button"
                onClick={onReset}
                className="rounded-2xl bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 ring-1 ring-white/10 hover:bg-white/8"
              >
                Back
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

