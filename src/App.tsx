import { useEffect, useMemo, useRef, useState } from 'react'
import heroImg from './assets/hero.png'

type Character = {
  id: string
  name: string
  description: string
  accent: string
}

type Scene = {
  id: string
  title: string
  shot: string
  dialogue: string
  prompt: string
  locked: boolean
}

type StoryPreview = {
  logline: string
  characters: Character[]
  scenes: Scene[]
}

type Step = 'input' | 'script' | 'preview' | 'video' | 'result'

type StylePreset = 'Anime' | 'Cinematic' | 'Cyberpunk' | '3D Cartoon' | 'Custom'

type CustomStyle = {
  mood: number
  camera: number
  lighting: number
  color: number
}

type RecentVideo = {
  id: string
  createdAt: number
  style: StylePreset
  pinned: boolean
  imageUrl: string
  videoUrl: string
  idea: string
  project: {
    idea: string
    selectedStyle: StylePreset
    customStyle: CustomStyle
    keepCharacterConsistency: boolean
    characterRefImageUrl: string | null
    story: StoryPreview
  }
}

const RECENT_VIDEOS_KEY = 'ai-storyteller:recent-videos:v1'

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n))
}

function useFakeProgress(enabled: boolean, durationMs: number, onDone: () => void) {
  const [progress, setProgress] = useState(0)
  const onDoneRef = useRef(onDone)

  useEffect(() => {
    onDoneRef.current = onDone
  }, [onDone])

  useEffect(() => {
    if (!enabled) return

    const start = Date.now()
    setProgress(0)

    const interval = window.setInterval(() => {
      const t = (Date.now() - start) / durationMs
      const eased = 1 - Math.pow(1 - clamp(t, 0, 1), 3)
      const next = Math.round(eased * 100)
      setProgress(next)

      if (t >= 1) {
        window.clearInterval(interval)
        setProgress(100)
        onDoneRef.current()
      }
    }, 60)

    return () => window.clearInterval(interval)
  }, [durationMs, enabled])

  return progress
}

function initials(name: string) {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function AppIcon() {
  return (
    <div className="relative grid h-10 w-10 place-items-center overflow-hidden rounded-2xl bg-gradient-to-br from-purple-500/35 via-slate-950/10 to-amber-300/30 shadow-[0_18px_40px_-26px_rgba(0,0,0,0.9)] ring-1 ring-white/12">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.18),transparent_55%)]" />
      <div className="pointer-events-none absolute -bottom-6 -right-6 h-14 w-14 rounded-full bg-amber-200/20 blur-2xl" />
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
        className="relative text-white/90"
      >
        <path
          d="M12 2l1.2 4.2c.2.7.8 1.3 1.5 1.5L19 9l-4.3 1.3c-.7.2-1.3.8-1.5 1.5L12 16l-1.2-4.2c-.2-.7-.8-1.3-1.5-1.5L5 9l4.3-1.3c.7-.2 1.3-.8 1.5-1.5L12 2Z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <path
          d="M18 13l.5 1.7c.1.4.4.7.8.8L21 16l-1.7.5c-.4.1-.7.4-.8.8L18 19l-.5-1.7c-.1-.4-.4-.7-.8-.8L15 16l1.7-.5c.4-.1.7-.4.8-.8L18 13Z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
          opacity="0.55"
        />
      </svg>
    </div>
  )
}

function SparkleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 2l1.2 4.2c.2.7.8 1.3 1.5 1.5L19 9l-4.3 1.3c-.7.2-1.3.8-1.5 1.5L12 16l-1.2-4.2c-.2-.7-.8-1.3-1.5-1.5L5 9l4.3-1.3c.7-.2 1.3-.8 1.5-1.5L12 2Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M19 13l.6 2.1c.1.4.4.7.8.8L22 16l-1.6.5c-.4.1-.7.4-.8.8L19 19l-.6-1.7c-.1-.4-.4-.7-.8-.8L16 16l1.6-.5c.4-.1.7-.4.8-.8L19 13Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 3h6m-8 4h10m-9 0l1 14h6l1-14"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M10 11v6m4-6v6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function Surface({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-[28px] bg-white/[0.055] shadow-[0_30px_120px_-60px_rgba(0,0,0,0.9)] ring-1 ring-white/10 backdrop-blur-md">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/8 via-transparent to-transparent" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(255,255,255,0.08),transparent_55%)]" />
      <div className="relative p-6 sm:p-9">{children}</div>
    </div>
  )
}

function readRecentVideos(): RecentVideo[] {
  try {
    const raw = window.localStorage.getItem(RECENT_VIDEOS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(Boolean)
      .map((v) => ({
        pinned: false,
        ...v,
      })) as RecentVideo[]
  } catch {
    return []
  }
}

function writeRecentVideos(videos: RecentVideo[]) {
  try {
    window.localStorage.setItem(RECENT_VIDEOS_KEY, JSON.stringify(videos.slice(0, 12)))
  } catch {
    return
  }
}

function formatTime(ts: number) {
  const d = new Date(ts)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}

function makeId() {
  const c = globalThis.crypto as Crypto | undefined
  if (c?.randomUUID) return c.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function App() {
  const [step, setStep] = useState<Step>('input')
  const [idea, setIdea] = useState('')
  const [story, setStory] = useState<StoryPreview | null>(null)
  const [draftStory, setDraftStory] = useState<StoryPreview | null>(null)
  const [baseStory, setBaseStory] = useState<StoryPreview | null>(null)
  const [selectedStyle, setSelectedStyle] = useState<StylePreset>('Cinematic')
  const [customStyle, setCustomStyle] = useState<CustomStyle>({
    mood: 55,
    camera: 55,
    lighting: 55,
    color: 55,
  })
  const [keepCharacterConsistency, setKeepCharacterConsistency] = useState(true)
  const [characterRefImageUrl, setCharacterRefImageUrl] = useState<string | null>(null)
  const [recentVideos, setRecentVideos] = useState<RecentVideo[]>([])
  const [dragSceneId, setDragSceneId] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [isCharacterEditorOpen, setIsCharacterEditorOpen] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const importInputRef = useRef<HTMLInputElement | null>(null)
  const characterImageInputRef = useRef<HTMLInputElement | null>(null)

  const canGenerate = idea.trim().length >= 10
  const stageLabel =
    step === 'input'
      ? 'Input'
      : step === 'script'
        ? 'Script'
        : step === 'preview'
          ? 'Preview'
          : step === 'video'
            ? 'Render'
            : 'Result'

  const demo = useMemo<StoryPreview>(() => {
    const base = idea.trim() || 'A short story about recovering a lost memory.'
    return {
      logline: base,
      characters: [
        {
          id: 'c1',
          name: 'Linh',
          description: 'Main character. Curious, decisive, carrying an old camera.',
          accent: 'from-purple-400 to-amber-200',
        },
        {
          id: 'c2',
          name: 'Star Dust',
          description: 'Mysterious guide with a warm voice, able to “lock” a character identity trace.',
          accent: 'from-amber-300 to-purple-300',
        },
      ],
      scenes: [
        {
          id: 's1',
          title: 'Opening',
          shot: 'Wide shot',
          dialogue: 'Linh: I’ve been here before… or was it just a dream?',
          prompt: 'Linh enters an abandoned train station; flickering lights; distant music echoing.',
          locked: false,
        },
        {
          id: 's2',
          title: 'Lock the Character',
          shot: 'Close-up',
          dialogue: 'Star Dust: To keep her consistent, we have to lock the identity trace.',
          prompt: 'Star Dust touches the camera; a luminous seal appears, confirming Linh’s identity.',
          locked: false,
        },
        {
          id: 's3',
          title: 'Transition',
          shot: 'Tracking shot',
          dialogue: 'Linh: Wait—those are my memories!',
          prompt: 'The corridor morphs into a starry sky; Linh runs after memories falling like meteors.',
          locked: false,
        },
      ],
    }
  }, [idea])

  useEffect(() => {
    setRecentVideos(readRecentVideos())
  }, [])

  const sampleVideoUrl = 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4'

  useEffect(() => {
    if (step === 'script' || step === 'video') {
      setJobId(makeId().slice(0, 8))
    } else {
      setJobId(null)
    }
  }, [step])

  const scriptProgress = useFakeProgress(step === 'script', 3000, () => {
    const generated = deepClone(demo)
    setStory(generated)
    setBaseStory(deepClone(generated))
    setDraftStory(deepClone(generated))
    setStep('preview')
  })

  const stylePresets: StylePreset[] = useMemo(
    () => ['Anime', 'Cinematic', 'Cyberpunk', '3D Cartoon', 'Custom'],
    [],
  )

  const stylePrompt = useMemo(() => {
    const preset =
      selectedStyle === 'Anime'
        ? 'anime keyframe animation, expressive faces, clean line art, vibrant but controlled palette'
        : selectedStyle === 'Cinematic'
          ? 'cinematic lighting, shallow depth of field, natural film grain, realistic textures'
          : selectedStyle === 'Cyberpunk'
            ? 'neon cyberpunk city, high contrast, glossy reflections, volumetric fog'
            : selectedStyle === '3D Cartoon'
              ? 'stylized 3D cartoon, soft shading, smooth surfaces, playful proportions'
              : ''

    if (selectedStyle !== 'Custom') return preset

    const mood =
      customStyle.mood < 34 ? 'calm, intimate' : customStyle.mood < 67 ? 'balanced, adventurous' : 'tense, dramatic'
    const camera =
      customStyle.camera < 34
        ? 'static camera, tripod framing'
        : customStyle.camera < 67
          ? 'handheld subtle motion'
          : 'dynamic camera movement, cinematic tracking'
    const lighting =
      customStyle.lighting < 34
        ? 'soft ambient lighting'
        : customStyle.lighting < 67
          ? 'balanced key light'
          : 'high-contrast rim lighting'
    const color =
      customStyle.color < 34
        ? 'desaturated, muted tones'
        : customStyle.color < 67
          ? 'natural color palette'
          : 'rich, stylized color grading'

    return [mood, camera, lighting, color].join(', ')
  }, [customStyle.camera, customStyle.color, customStyle.lighting, customStyle.mood, selectedStyle])

  const updateScene = (sceneId: string, field: 'dialogue' | 'prompt', value: string) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        scenes: prev.scenes.map((s) => (s.id === sceneId ? { ...s, [field]: value } : s)),
      }
    })
  }

  const updateSceneMeta = (sceneId: string, field: 'title' | 'shot', value: string) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        scenes: prev.scenes.map((s) => (s.id === sceneId ? { ...s, [field]: value } : s)),
      }
    })
  }

  const toggleSceneLock = (sceneId: string) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        scenes: prev.scenes.map((s) => (s.id === sceneId ? { ...s, locked: !s.locked } : s)),
      }
    })
  }

  const resetScene = (sceneId: string) => {
    setDraftStory((prev) => {
      if (!prev || !baseStory) return prev
      const base = baseStory.scenes.find((s) => s.id === sceneId)
      if (!base) return prev
      return {
        ...prev,
        scenes: prev.scenes.map((s) =>
          s.id === sceneId ? { ...s, dialogue: base.dialogue, prompt: base.prompt } : s,
        ),
      }
    })
  }

  const removeScene = (sceneId: string) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      return { ...prev, scenes: prev.scenes.filter((s) => s.id !== sceneId) }
    })
  }

  const duplicateScene = (sceneId: string) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      const idx = prev.scenes.findIndex((s) => s.id === sceneId)
      if (idx < 0) return prev
      const copy = { ...prev.scenes[idx], id: makeId() }
      const next = [...prev.scenes.slice(0, idx + 1), copy, ...prev.scenes.slice(idx + 1)]
      return { ...prev, scenes: next }
    })
  }

  const addScene = () => {
    setDraftStory((prev) => {
      if (!prev) return prev
      const n = prev.scenes.length + 1
      const nextScene: Scene = {
        id: makeId(),
        title: `Scene ${n}`,
        shot: 'Medium shot',
        dialogue: '',
        prompt: '',
        locked: false,
      }
      return { ...prev, scenes: [...prev.scenes, nextScene] }
    })
  }

  const reorderScene = (fromId: string, toId: string) => {
    if (fromId === toId) return
    setDraftStory((prev) => {
      if (!prev) return prev
      const from = prev.scenes.findIndex((s) => s.id === fromId)
      const to = prev.scenes.findIndex((s) => s.id === toId)
      if (from < 0 || to < 0) return prev
      const next = [...prev.scenes]
      const [moved] = next.splice(from, 1)
      next.splice(to, 0, moved)
      return { ...prev, scenes: next }
    })
  }

  const moveScene = (sceneId: string, dir: -1 | 1) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      const idx = prev.scenes.findIndex((s) => s.id === sceneId)
      if (idx < 0) return prev
      const to = idx + dir
      if (to < 0 || to >= prev.scenes.length) return prev
      const next = [...prev.scenes]
      const [moved] = next.splice(idx, 1)
      next.splice(to, 0, moved)
      return { ...prev, scenes: next }
    })
  }

  const sortedRecentVideos = useMemo(() => {
    const list = [...recentVideos]
    list.sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
      return b.createdAt - a.createdAt
    })
    return list
  }, [recentVideos])

  const pinRecent = (id: string) => {
    setRecentVideos((prev) => {
      const next = prev.map((v) => (v.id === id ? { ...v, pinned: !v.pinned } : v))
      writeRecentVideos(next)
      return next
    })
  }

  const removeRecent = (id: string) => {
    setRecentVideos((prev) => {
      const next = prev.filter((v) => v.id !== id)
      writeRecentVideos(next)
      return next
    })
  }

  const clearRecent = () => {
    setRecentVideos([])
    writeRecentVideos([])
  }

  const openProject = (v: RecentVideo) => {
    setIdea(v.project.idea)
    setSelectedStyle(v.project.selectedStyle)
    setCustomStyle(v.project.customStyle)
    setKeepCharacterConsistency(v.project.keepCharacterConsistency)
    setCharacterRefImageUrl(v.project.characterRefImageUrl)
    setStory(deepClone(v.project.story))
    setBaseStory(deepClone(v.project.story))
    setDraftStory(deepClone(v.project.story))
    setStep('preview')
  }

  const exportProject = () => {
    const projectStory = draftStory ?? story
    if (!projectStory) return

    const payload = {
      version: 1,
      idea: idea.trim(),
      selectedStyle,
      customStyle,
      keepCharacterConsistency,
      characterRefImageUrl,
      stylePrompt,
      story: projectStory,
    }

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-storyteller-project-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const copyProjectJson = async () => {
    const projectStory = draftStory ?? story
    if (!projectStory) return
    const payload = {
      version: 1,
      idea: idea.trim(),
      selectedStyle,
      customStyle,
      keepCharacterConsistency,
      characterRefImageUrl,
      stylePrompt,
      story: projectStory,
    }
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
  }

  const importProjectText = (text: string) => {
    try {
      const data = JSON.parse(text) as any
      const importedStory = data?.story as StoryPreview | undefined
      if (!importedStory || !Array.isArray(importedStory.scenes) || !Array.isArray(importedStory.characters)) {
        throw new Error('Invalid project schema')
      }

      setIdea(String(data?.idea ?? ''))
      setSelectedStyle((data?.selectedStyle as StylePreset) ?? 'Cinematic')
      setCustomStyle(
        (data?.customStyle as CustomStyle) ?? {
          mood: 55,
          camera: 55,
          lighting: 55,
          color: 55,
        },
      )
      setKeepCharacterConsistency(Boolean(data?.keepCharacterConsistency ?? true))
      setCharacterRefImageUrl((data?.characterRefImageUrl as string | null) ?? null)

      const normalized: StoryPreview = {
        ...importedStory,
        scenes: importedStory.scenes.map((s) => ({
          ...s,
          locked: Boolean((s as any).locked ?? false),
        })),
      }

      setStory(deepClone(normalized))
      setBaseStory(deepClone(normalized))
      setDraftStory(deepClone(normalized))
      setImportError(null)
      setStep('preview')
    } catch {
      setImportError('Import failed. Please select a valid project JSON.')
    }
  }

  const uploadCharacterRefImage = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : null
      setCharacterRefImageUrl(result)
    }
    reader.readAsDataURL(file)
  }

  const updateCharacter = (id: string, field: 'name' | 'description', value: string) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        characters: prev.characters.map((c) => (c.id === id ? { ...c, [field]: value } : c)),
      }
    })
  }

  const addCharacter = () => {
    setDraftStory((prev) => {
      if (!prev) return prev
      const next = {
        id: makeId(),
        name: `Character ${prev.characters.length + 1}`,
        description: '',
        accent: 'from-purple-400 to-amber-200',
      }
      return { ...prev, characters: [...prev.characters, next] }
    })
  }

  const removeCharacter = (id: string) => {
    setDraftStory((prev) => {
      if (!prev) return prev
      return { ...prev, characters: prev.characters.filter((c) => c.id !== id) }
    })
  }

  const videoProgress = useFakeProgress(step === 'video', 6000, () => {
    const trimmedIdea = idea.trim()
    const projectStory = deepClone(draftStory ?? story ?? demo)
    const imageUrl = characterRefImageUrl ?? heroImg
    const newItem: RecentVideo = {
      id: makeId(),
      createdAt: Date.now(),
      style: selectedStyle,
      pinned: false,
      imageUrl,
      videoUrl: sampleVideoUrl,
      idea: trimmedIdea,
      project: {
        idea: trimmedIdea,
        selectedStyle,
        customStyle,
        keepCharacterConsistency,
        characterRefImageUrl,
        story: projectStory,
      },
    }

    setRecentVideos((prev) => {
      const next = [newItem, ...prev].slice(0, 12)
      writeRecentVideos(next)
      return next
    })
    setStep('result')
  })

  return (
    <div className="min-h-full bg-slate-950 text-slate-50 selection:bg-amber-400/25">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-56 left-[55%] h-[760px] w-[760px] -translate-x-1/2 rounded-full bg-purple-400/12 blur-[120px]" />
        <div className="absolute -bottom-72 left-[18%] h-[820px] w-[820px] -translate-x-1/2 rounded-full bg-amber-300/10 blur-[140px]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.06),transparent_55%)]" />
      </div>

      <div className="relative mx-auto flex min-h-full w-full max-w-5xl flex-col px-4 py-8 sm:px-6 sm:py-10">
        <header className="flex flex-col gap-2">
          <div className="inline-flex items-center gap-3">
            <AppIcon />
            <div className="text-sm font-semibold tracking-tight text-slate-100 sm:text-base">AI Storyteller</div>
            <div className="ml-auto inline-flex items-center gap-2 text-xs text-slate-300">
              <span className="rounded-full bg-white/5 px-3 py-1 ring-1 ring-white/10">
                Stage: {stageLabel}
              </span>
            </div>
          </div>
        </header>

        <main className="mt-8 flex-1">
          <div className="space-y-6">
            <Surface>
              {step === 'input' && (
                <div className="grid gap-7 lg:grid-cols-[1.25fr_0.75fr]">
                  <div className="space-y-4">
                    <div className="text-sm leading-6 text-slate-300">
                      Describe your story idea. Generate a storyboard and locked character set, then review before rendering video.
                    </div>

                    <textarea
                      value={idea}
                      onChange={(e) => setIdea(e.target.value)}
                      placeholder="Example: A girl searches for a lost memory in a rainy city..."
                      spellCheck={false}
                      className="h-44 w-full resize-none rounded-2xl bg-slate-900/35 px-4 py-3 text-sm leading-6 text-slate-100 ring-1 ring-white/8 outline-none placeholder:text-slate-500 focus:ring-2 focus:ring-amber-200/35"
                    />

                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        disabled={!canGenerate}
                        onClick={() => setStep('script')}
                        className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-b from-amber-200/85 to-amber-200/55 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_14px_30px_-18px_rgba(255,196,115,0.55)] ring-1 ring-amber-100/35 transition enabled:hover:from-amber-200 enabled:hover:to-amber-200/70 disabled:cursor-not-allowed disabled:from-amber-200/30 disabled:to-amber-200/20 disabled:text-slate-950/50"
                      >
                        <SparkleIcon />
                        Gen
                      </button>
                      <button
                        type="button"
                        onClick={() => setIdea('')}
                        className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white/5 px-5 py-2.5 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                      >
                        <TrashIcon />
                        Clear
                      </button>
                      <div className="text-xs leading-5 text-slate-400">Minimum: 10 characters.</div>
                    </div>
                  </div>

                  <div className="rounded-2xl bg-slate-900/30 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="text-sm font-semibold tracking-tight text-slate-100">Structure</div>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {stylePresets.map((s) => (
                          <button
                            key={s}
                            type="button"
                            onClick={() => setSelectedStyle(s)}
                            className={[
                              'rounded-full px-3 py-1 text-xs font-semibold ring-1 transition',
                              s === selectedStyle
                                ? 'bg-white/12 text-slate-100 ring-white/15'
                                : 'bg-white/5 text-slate-300 ring-white/10 hover:bg-white/8',
                            ].join(' ')}
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="mt-3 space-y-3 text-sm leading-6 text-slate-300">
                      <div className="rounded-xl bg-white/5 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10">
                        <ol className="grid gap-1.5 text-sm leading-6 text-slate-300">
                          <li className="flex items-start gap-2">
                            <div className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-lg bg-white/7 text-[11px] font-semibold text-slate-200 ring-1 ring-white/10">
                              1
                            </div>
                            <div className="min-w-0">
                              <span className="font-semibold text-slate-100">Logline</span> — 1 sentence
                            </div>
                          </li>
                          <li className="flex items-start gap-2">
                            <div className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-lg bg-white/7 text-[11px] font-semibold text-slate-200 ring-1 ring-white/10">
                              2
                            </div>
                            <div className="min-w-0">
                              <span className="font-semibold text-slate-100">Characters</span> — 2 leads
                            </div>
                          </li>
                          <li className="flex items-start gap-2">
                            <div className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-lg bg-white/7 text-[11px] font-semibold text-slate-200 ring-1 ring-white/10">
                              3
                            </div>
                            <div className="min-w-0">
                              <span className="font-semibold text-slate-100">Scenes</span> — 3–5 shorts
                            </div>
                          </li>
                        </ol>
                      </div>
                      {selectedStyle === 'Custom' && (
                        <div className="rounded-xl bg-white/5 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10">
                          <div className="grid gap-3">
                            <div className="flex items-center justify-between text-xs text-slate-300">
                              <div>Mood</div>
                              <div className="text-slate-400">{customStyle.mood}</div>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={customStyle.mood}
                              onChange={(e) => setCustomStyle((p) => ({ ...p, mood: Number(e.target.value) }))}
                              className="w-full accent-amber-200"
                            />

                            <div className="flex items-center justify-between text-xs text-slate-300">
                              <div>Camera</div>
                              <div className="text-slate-400">{customStyle.camera}</div>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={customStyle.camera}
                              onChange={(e) => setCustomStyle((p) => ({ ...p, camera: Number(e.target.value) }))}
                              className="w-full accent-amber-200"
                            />

                            <div className="flex items-center justify-between text-xs text-slate-300">
                              <div>Lighting</div>
                              <div className="text-slate-400">{customStyle.lighting}</div>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={customStyle.lighting}
                              onChange={(e) => setCustomStyle((p) => ({ ...p, lighting: Number(e.target.value) }))}
                              className="w-full accent-amber-200"
                            />

                            <div className="flex items-center justify-between text-xs text-slate-300">
                              <div>Color</div>
                              <div className="text-slate-400">{customStyle.color}</div>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={customStyle.color}
                              onChange={(e) => setCustomStyle((p) => ({ ...p, color: Number(e.target.value) }))}
                              className="w-full accent-amber-200"
                            />

                            <div className="text-xs leading-5 text-slate-400">{stylePrompt}</div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

            {step === 'script' && (
              <div className="space-y-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold tracking-tight text-slate-100">Generating script…</div>
                    <div className="mt-1 text-sm leading-6 text-slate-300">
                      Job {jobId ?? '—'} •{' '}
                      {scriptProgress < 34
                        ? 'Parsing idea'
                        : scriptProgress < 67
                          ? 'Drafting storyboard'
                          : 'Finalizing'}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setStep('input')
                      setJobId(null)
                    }}
                    className="inline-flex items-center justify-center rounded-2xl bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                  >
                    Cancel
                  </button>
                </div>

                <div className="rounded-2xl bg-slate-900/35 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10">
                  <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs text-slate-200 ring-1 ring-white/10">
                    <div className="h-3 w-3 animate-spin rounded-full border-2 border-white/20 border-t-white/70" />
                    Working…
                  </div>
                  <div className="flex items-center justify-between text-xs text-slate-300">
                    <div>Progress</div>
                    <div>{scriptProgress}%</div>
                  </div>
                  <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-purple-300/90 via-amber-200/90 to-amber-100/90 transition-[width]"
                      style={{ width: `${scriptProgress}%` }}
                    />
                  </div>
                </div>
              </div>
            )}

            {step === 'preview' && draftStory && (
              <div className="space-y-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold tracking-tight text-slate-100">Preview</div>
                    <div className="mt-1 text-sm leading-6 text-slate-300">
                      Style: {selectedStyle}
                      {stylePrompt ? ` • ${stylePrompt}` : ''}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setStep('video')}
                      className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-b from-amber-200/85 to-amber-200/55 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_14px_30px_-18px_rgba(255,196,115,0.55)] ring-1 ring-amber-100/35 transition hover:from-amber-200 hover:to-amber-200/70"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M10 8l6 4-6 4V8Z" fill="currentColor" />
                        <path
                          d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z"
                          stroke="currentColor"
                          strokeWidth="2"
                        />
                      </svg>
                      Render
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setStep('input')
                      }}
                      className="inline-flex items-center justify-center rounded-2xl bg-white/5 px-5 py-2.5 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                    >
                      Back
                    </button>

                    <button
                      type="button"
                      onClick={exportProject}
                      className="inline-flex items-center justify-center rounded-2xl bg-white/5 px-4 py-2.5 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                    >
                      Export JSON
                    </button>

                    <button
                      type="button"
                      onClick={() => void copyProjectJson()}
                      className="inline-flex items-center justify-center rounded-2xl bg-white/5 px-4 py-2.5 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                    >
                      Copy JSON
                    </button>

                    <button
                      type="button"
                      onClick={() => importInputRef.current?.click()}
                      className="inline-flex items-center justify-center rounded-2xl bg-white/5 px-4 py-2.5 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                    >
                      Import
                    </button>
                    <input
                      ref={importInputRef}
                      type="file"
                      accept="application/json"
                      className="hidden"
                      onChange={async (e) => {
                        const f = e.target.files?.[0]
                        if (!f) return
                        const text = await f.text()
                        importProjectText(text)
                        e.target.value = ''
                      }}
                    />
                  </div>
                </div>

                {importError && <div className="text-sm text-rose-200">{importError}</div>}

                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="rounded-2xl bg-slate-900/35 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10 lg:col-span-2">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-sm font-semibold tracking-tight text-slate-100">Storyboard</div>
                      <button
                        type="button"
                        onClick={addScene}
                        className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                      >
                        + Add scene
                      </button>
                    </div>

                    <div className="mt-3 space-y-3">
                      {draftStory.scenes.map((scene) => (
                        <div
                          key={scene.id}
                          draggable
                          onDragStart={() => setDragSceneId(scene.id)}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => {
                            if (dragSceneId) reorderScene(dragSceneId, scene.id)
                            setDragSceneId(null)
                          }}
                          className="rounded-2xl bg-white/5 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                              <div className="select-none text-xs text-slate-500">⋮⋮</div>
                              <input
                                value={scene.title}
                                onChange={(e) => updateSceneMeta(scene.id, 'title', e.target.value)}
                                className="min-w-0 flex-1 rounded-xl bg-transparent px-2 py-1 text-sm font-semibold text-slate-100 outline-none ring-1 ring-transparent focus:ring-white/15"
                                spellCheck={false}
                              />
                              <select
                                value={scene.shot}
                                onChange={(e) => updateSceneMeta(scene.id, 'shot', e.target.value)}
                                className="rounded-xl bg-slate-950/25 px-2 py-1 text-xs text-slate-200 ring-1 ring-white/10 outline-none"
                              >
                                {['Wide shot', 'Medium shot', 'Close-up', 'Tracking shot'].map((s) => (
                                  <option key={s} value={s}>
                                    {s}
                                  </option>
                                ))}
                              </select>
                              {scene.locked && (
                                <div className="rounded-full bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-200 ring-1 ring-emerald-400/20">
                                  Locked
                                </div>
                              )}
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => moveScene(scene.id, -1)}
                                className="rounded-full bg-white/5 px-2.5 py-1 text-xs font-semibold text-slate-200 ring-1 ring-white/10 transition hover:bg-white/8"
                              >
                                ↑
                              </button>
                              <button
                                type="button"
                                onClick={() => moveScene(scene.id, 1)}
                                className="rounded-full bg-white/5 px-2.5 py-1 text-xs font-semibold text-slate-200 ring-1 ring-white/10 transition hover:bg-white/8"
                              >
                                ↓
                              </button>
                              <button
                                type="button"
                                onClick={() => toggleSceneLock(scene.id)}
                                className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200 ring-1 ring-white/10 transition hover:bg-white/8"
                              >
                                {scene.locked ? 'Unlock' : 'Lock'}
                              </button>
                              <button
                                type="button"
                                onClick={() => resetScene(scene.id)}
                                className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200 ring-1 ring-white/10 transition hover:bg-white/8"
                              >
                                Reset
                              </button>
                              <button
                                type="button"
                                onClick={() => duplicateScene(scene.id)}
                                className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200 ring-1 ring-white/10 transition hover:bg-white/8"
                              >
                                Duplicate
                              </button>
                              <button
                                type="button"
                                onClick={() => removeScene(scene.id)}
                                className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-rose-200 ring-1 ring-white/10 transition hover:bg-white/8"
                              >
                                Delete
                              </button>
                            </div>
                          </div>

                          <div className="mt-4 grid gap-3">
                            <div>
                              <div className="mb-1 text-xs font-semibold text-slate-300">Dialogue</div>
                              <textarea
                                value={scene.dialogue}
                                onChange={(e) => updateScene(scene.id, 'dialogue', e.target.value)}
                                disabled={scene.locked}
                                spellCheck={false}
                                className="min-h-16 w-full resize-y rounded-2xl bg-slate-950/25 px-3 py-2 text-sm leading-6 text-slate-100 ring-1 ring-white/10 outline-none placeholder:text-slate-500 focus:ring-2 focus:ring-amber-200/35 disabled:opacity-60"
                              />
                            </div>
                            <div>
                              <div className="mb-1 text-xs font-semibold text-slate-300">Prompt</div>
                              <textarea
                                value={scene.prompt}
                                onChange={(e) => updateScene(scene.id, 'prompt', e.target.value)}
                                disabled={scene.locked}
                                spellCheck={false}
                                className="min-h-20 w-full resize-y rounded-2xl bg-slate-950/25 px-3 py-2 text-sm leading-6 text-slate-100 ring-1 ring-white/10 outline-none placeholder:text-slate-500 focus:ring-2 focus:ring-amber-200/35 disabled:opacity-60"
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl bg-slate-900/35 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-sm font-semibold tracking-tight text-slate-100">Characters</div>
                      <button
                        type="button"
                        onClick={() => setIsCharacterEditorOpen(true)}
                        className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                      >
                        Edit sheet
                      </button>
                    </div>

                    <div className="mt-3 flex items-center justify-between gap-3 rounded-2xl bg-white/5 px-4 py-3 ring-1 ring-white/10">
                      <div className="text-xs font-semibold text-slate-200">Character consistency</div>
                      <button
                        type="button"
                        onClick={() => setKeepCharacterConsistency((v) => !v)}
                        className={[
                          'h-7 w-12 rounded-full p-1 ring-1 transition',
                          keepCharacterConsistency ? 'bg-emerald-500/30 ring-emerald-300/20' : 'bg-white/8 ring-white/10',
                        ].join(' ')}
                      >
                        <div
                          className={[
                            'h-5 w-5 rounded-full bg-white/90 transition',
                            keepCharacterConsistency ? 'translate-x-5' : 'translate-x-0',
                          ].join(' ')}
                        />
                      </button>
                    </div>

                    <div className="mt-3 rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-xs font-semibold text-slate-200">Reference image</div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => characterImageInputRef.current?.click()}
                            className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                          >
                            Upload
                          </button>
                          <button
                            type="button"
                            onClick={() => setCharacterRefImageUrl(null)}
                            className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                      <input
                        ref={characterImageInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (f) uploadCharacterRefImage(f)
                          e.target.value = ''
                        }}
                      />
                      <div className="mt-3 overflow-hidden rounded-2xl bg-black/20 ring-1 ring-white/10">
                        <img src={characterRefImageUrl ?? heroImg} alt="" className="h-28 w-full object-cover opacity-90" />
                      </div>
                    </div>

                    <div className="mt-3 space-y-3">
                      {draftStory.characters.map((c) => (
                        <div
                          key={c.id}
                          className="rounded-2xl bg-white/5 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10"
                        >
                          <div className="flex items-start gap-3">
                            <div
                              className={`grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br ${c.accent} text-sm font-bold text-white ring-1 ring-white/10`}
                            >
                              {initials(c.name)}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm font-semibold text-slate-100">{c.name}</div>
                              <div className="mt-1 text-sm leading-6 text-slate-300">{c.description}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {isCharacterEditorOpen && (
                  <div className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-4">
                    <div className="w-full max-w-2xl overflow-hidden rounded-3xl bg-slate-950/80 ring-1 ring-white/10 backdrop-blur-xl">
                      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
                        <div className="text-sm font-semibold tracking-tight text-slate-100">Character sheet</div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={addCharacter}
                            className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                          >
                            + Add
                          </button>
                          <button
                            type="button"
                            onClick={() => setIsCharacterEditorOpen(false)}
                            className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                          >
                            Done
                          </button>
                        </div>
                      </div>

                      <div className="max-h-[70vh] space-y-3 overflow-auto p-5">
                        {draftStory.characters.map((c) => (
                          <div key={c.id} className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <div className="text-xs font-semibold text-slate-300">Name</div>
                                <input
                                  value={c.name}
                                  onChange={(e) => updateCharacter(c.id, 'name', e.target.value)}
                                  className="mt-1 w-full rounded-2xl bg-slate-950/25 px-3 py-2 text-sm leading-6 text-slate-100 ring-1 ring-white/10 outline-none focus:ring-2 focus:ring-amber-200/35"
                                  spellCheck={false}
                                />
                                <div className="mt-3 text-xs font-semibold text-slate-300">Description</div>
                                <textarea
                                  value={c.description}
                                  onChange={(e) => updateCharacter(c.id, 'description', e.target.value)}
                                  className="mt-1 min-h-20 w-full resize-y rounded-2xl bg-slate-950/25 px-3 py-2 text-sm leading-6 text-slate-100 ring-1 ring-white/10 outline-none focus:ring-2 focus:ring-amber-200/35"
                                  spellCheck={false}
                                />
                              </div>
                              <button
                                type="button"
                                onClick={() => removeCharacter(c.id)}
                                className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-rose-200 ring-1 ring-white/10 transition hover:bg-white/8"
                              >
                                Delete
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {step === 'video' && (
              <div className="space-y-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold tracking-tight text-slate-100">Rendering video…</div>
                    <div className="mt-1 text-sm leading-6 text-slate-300">
                      Job {jobId ?? '—'} •{' '}
                      {videoProgress < 34 ? 'Preparing assets' : videoProgress < 67 ? 'Rendering clips' : 'Finalizing'}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setStep('preview')
                      setJobId(null)
                    }}
                    className="inline-flex items-center justify-center rounded-2xl bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                  >
                    Cancel
                  </button>
                </div>

                <div className="rounded-2xl bg-slate-900/35 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10">
                  <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs text-slate-200 ring-1 ring-white/10">
                    <div className="h-3 w-3 animate-spin rounded-full border-2 border-white/20 border-t-white/70" />
                    Working…
                  </div>
                  <div className="flex items-center justify-between text-xs text-slate-300">
                    <div>Progress</div>
                    <div>{videoProgress}%</div>
                  </div>
                  <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-purple-200/90 via-amber-200/90 to-amber-100/90 transition-[width]"
                      style={{ width: `${videoProgress}%` }}
                    />
                  </div>
                </div>
              </div>
            )}

            {step === 'result' && (
              <div className="space-y-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold tracking-tight text-slate-100">Final video</div>
                    <div className="mt-1 text-sm leading-6 text-slate-300">Style: {selectedStyle}</div>
                  </div>

                  <div className="flex items-center gap-3">
                    <a
                      href={sampleVideoUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-b from-amber-200/85 to-amber-200/55 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_14px_30px_-18px_rgba(255,196,115,0.55)] ring-1 ring-amber-100/35 transition hover:from-amber-200 hover:to-amber-200/70"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M12 3v10m0 0l4-4m-4 4l-4-4"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                        <path
                          d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                      Download
                    </a>
                    <button
                      type="button"
                      onClick={() => {
                        setIdea('')
                        setStory(null)
                        setDraftStory(null)
                        setBaseStory(null)
                        setStep('input')
                      }}
                      className="inline-flex items-center justify-center rounded-2xl bg-white/5 px-5 py-2.5 text-sm font-semibold text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] ring-1 ring-white/10 transition hover:bg-white/8"
                    >
                      New project
                    </button>
                  </div>
                </div>

                <div className="overflow-hidden rounded-3xl bg-slate-900/35 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-white/10">
                  <div className="aspect-video w-full bg-black/30">
                    <video className="h-full w-full" controls preload="metadata" src={sampleVideoUrl} />
                  </div>
                </div>
              </div>
            )}
            </Surface>

            {sortedRecentVideos.length > 0 && (
              <div className="rounded-[22px] bg-white/[0.035] px-4 py-4 shadow-[0_20px_80px_-55px_rgba(0,0,0,0.85)] ring-1 ring-white/10 backdrop-blur-md sm:px-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold tracking-tight text-slate-100">Recent videos</div>
                    <div className="text-xs text-slate-400">Stored locally in your browser</div>
                  </div>
                  <button
                    type="button"
                    onClick={clearRecent}
                    className="rounded-full bg-white/5 px-3 py-1 text-xs font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                  >
                    Clear all
                  </button>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {sortedRecentVideos.map((v) => (
                    <div
                      key={v.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => openProject(v)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') openProject(v)
                      }}
                      className="group overflow-hidden rounded-2xl bg-white/5 text-left ring-1 ring-white/10 transition hover:bg-white/8"
                    >
                      <div className="relative aspect-[16/9] w-full overflow-hidden bg-black/20">
                        <img
                          src={v.imageUrl}
                          alt=""
                          className="h-full w-full object-cover opacity-85 transition group-hover:opacity-100"
                        />
                        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
                        <div className="absolute bottom-2 left-2 inline-flex items-center gap-2 rounded-full bg-black/45 px-2.5 py-1 text-[11px] font-semibold text-slate-100 ring-1 ring-white/10">
                          <span>{v.style}</span>
                          <span className="h-1 w-1 rounded-full bg-white/35" />
                          <span>{formatTime(v.createdAt)}</span>
                        </div>
                        <div className="absolute right-2 top-2 flex items-center gap-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              pinRecent(v.id)
                            }}
                            className={[
                              'rounded-full px-2.5 py-1 text-xs font-semibold ring-1 transition',
                              v.pinned
                                ? 'bg-amber-200/20 text-amber-100 ring-amber-100/25'
                                : 'bg-black/35 text-slate-100 ring-white/10 hover:bg-black/45',
                            ].join(' ')}
                          >
                            {v.pinned ? 'Pinned' : 'Pin'}
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              removeRecent(v.id)
                            }}
                            className="rounded-full bg-black/35 px-2.5 py-1 text-xs font-semibold text-rose-200 ring-1 ring-white/10 transition hover:bg-black/45"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                      <div className="p-3">
                        <div className="max-h-10 overflow-hidden text-xs leading-5 text-slate-300">
                          {v.idea || 'Untitled'}
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2">
                          <div className="text-[11px] font-semibold text-slate-400">Open project</div>
                          <a
                            href={v.videoUrl}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="rounded-full bg-white/5 px-3 py-1 text-[11px] font-semibold text-slate-100 ring-1 ring-white/10 transition hover:bg-white/8"
                          >
                            Open video
                          </a>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
