export type ProjectOut = {
  id: string
  topic: string
  target_duration_seconds: number
  state: string
  blueprint_present: boolean
  created_at: string
  updated_at: string
}

export type PipelineStageRunOut = {
  id: string
  stage: string
  status: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export type PipelineRunOut = {
  id: string
  project_id: string
  status: string
  current_stage: string | null
  idempotency_key: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  stage_runs: PipelineStageRunOut[]
  log_summary: string[]
}

export type PipelineRunStartResponse = {
  created: boolean
  run: PipelineRunOut
}

export type AssetOut = {
  id: string
  project_id: string
  scene_id: string | null
  asset_type: string
  provider: string | null
  uri: string
  metadata_json: Record<string, unknown> | null
  created_at: string
}

export type SceneOut = {
  id: string
  project_id: string
  scene_number: number
  narration_script: string | null
  image_generation_prompt: string | null
  camera_movement_suggestion: string | null
  estimated_duration_seconds: number | null
  status: string
  created_at: string
  updated_at: string
  assets: AssetOut[]
}

export type ProjectResultOut = {
  mp4_url: string | null
  hls_master_url: string | null
}

function apiBase() {
  const env = (import.meta as any).env as Record<string, string | undefined>
  return (env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '')
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status} ${res.statusText}${text ? `: ${text}` : ''}`)
  }
  return (await res.json()) as T
}

export async function createProject(topic: string, targetDurationSeconds: number): Promise<ProjectOut> {
  return http<ProjectOut>('/projects', {
    method: 'POST',
    body: JSON.stringify({ topic, target_duration_seconds: targetDurationSeconds }),
  })
}

export async function startRun(projectId: string): Promise<PipelineRunStartResponse> {
  return http<PipelineRunStartResponse>(`/projects/${projectId}/runs`, { method: 'POST' })
}

export async function getRun(projectId: string, runId: string): Promise<PipelineRunOut> {
  return http<PipelineRunOut>(`/projects/${projectId}/runs/${runId}`)
}

export async function getScenes(projectId: string): Promise<SceneOut[]> {
  return http<SceneOut[]>(`/projects/${projectId}/scenes`)
}

export async function getResult(projectId: string): Promise<ProjectResultOut> {
  return http<ProjectResultOut>(`/projects/${projectId}/result`)
}

