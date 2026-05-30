# App Integration Plan (VideoSup + Web + Backend + .trae)

## Summary
- Goal: turn the existing repo into an end-to-end “AI storytelling → short video” app by wiring **web/** (UI) to **backend/** (FastAPI + Celery) and using **PixVerse** for clip generation plus **VideoSup** for FFmpeg stitching/subtitles.
- MVP decisions (from user):
  - Mode: **Hybrid** (mock LLM/TTS/T2I where needed, PixVerse for video)
  - VideoSup: **run as a separate service**
  - Web: **real API integration** (no fake progress / local-only demo flow)

## Current State Analysis (grounded in repo)
### backend/
- FastAPI project + run endpoints exist in [api/main.py](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/backend/api/main.py).
  - Projects: `POST /projects`, `GET /projects`, `GET /projects/{id}`
  - Blueprint: `GET/PUT /projects/{id}/blueprint`
  - Runs: `POST /projects/{id}/runs`, `GET /projects/{id}/runs/{run_id}`, `GET /runs/{run_id}`
- Celery pipeline exists in [worker/tasks.py](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/backend/worker/tasks.py):
  - Stages: `GENERATE_BLUEPRINT` → `GENERATE_ASSETS` → `RENDER_ASSEMBLE`
  - `RENDER_ASSEMBLE` currently only flips states to COMPLETED (no stitching).
- Provider abstraction exists in [shared/providers/interfaces.py](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/backend/shared/providers/interfaces.py) and mock implementations exist in [shared/providers/mock.py](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/backend/shared/providers/mock.py).
- DB schema supports Projects/Scenes/Assets/Runs in [shared/persistence/models.py](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/backend/shared/persistence/models.py).

### web/
- A Vite + React UI exists but it is currently a self-contained demo with fake progress and localStorage (no backend calls) in [src/App.tsx](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/web/src/App.tsx).

### VideoSup/
- Contains a functional FFmpeg stitching/subtitles pipeline as a Python library in [videosup_worker/pipeline/pipeline.py](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/VideoSup/worker/videosup_worker/pipeline/pipeline.py).
- Defines a media job contract in [media-contract.md](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/VideoSup/media-contract.md).
- Docker compose currently brings up MinIO and a “worker” container that runs tests (not a long-running service) in [VideoSup/docker-compose.yml](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/VideoSup/docker-compose.yml) and [VideoSup/worker/Dockerfile](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/VideoSup/worker/Dockerfile).

### .trae/
- Contains design rules and an implemented backend spec that already matches today’s backend structure: [spec.md](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/.trae/specs/build-fastapi-celery-worker-backend/spec.md).

## Target Architecture (MVP)
- Web UI (React) calls Backend API.
- Backend worker runs pipeline:
  - Generate blueprint (mock LLM ok for MVP)
  - Generate scene video clips via PixVerse (treat PixVerse as “video generation engine”)
  - Submit stitching/subtitles job to VideoSup Service, poll until done
  - Persist all artifacts and expose them via API so Web can render progress + final video

## Proposed Changes (Decision-Complete)
### 1) Backend: add PixVerse-backed video provider (hybrid mode)
**Why:** today the backend only has mock providers; hybrid MVP needs real clips.

**Files**
- Add: `backend/shared/providers/pixverse.py` (new provider implementation)
- Update: `backend/shared/providers/factory.py` (select provider based on env)
- Update: `backend/shared/config.py` (add PixVerse settings)

**Implementation details**
- Add env-driven configuration (names are proposed, finalize in code):
  - `PIXVERSE_API_KEY` (required in hybrid mode)
  - `PIXVERSE_MODEL` (default `v6`)
  - `PIXVERSE_ASPECT_RATIO` (default `9:16`)
  - `PIXVERSE_QUALITY` (default `720p`)
  - `PIXVERSE_DURATION_SEC` (default `5`)
  - `PIXVERSE_POLL_INTERVAL_SEC` (default `5`)
  - `PIXVERSE_MAX_POLL_SEC` (default `300`)
- Use `httpx` (already in backend requirements) to:
  - `POST https://app-api.pixverse.ai/openapi/v2/video/text/generate`
  - Poll `GET https://app-api.pixverse.ai/openapi/v2/video/result/{video_id}`
- Provider output (`GeneratedAsset.uri`) becomes a downloadable MP4 URL.

**Key design choice for hybrid**
- Keep the backend’s provider interface unchanged by passing a “prompt URI” when no real image exists:
  - In `stage_generate_assets`, when using PixVerse provider:
    - Pass `image_uri = "prompt://<urlencoded scene.image_generation_prompt>"`
    - Pass `motion_prompt = scene.camera_movement_suggestion or "minimal camera motion"`
  - PixVerse provider behavior:
    - If `image_uri` starts with `prompt://`, ignore image-to-video and call PixVerse **text-to-video** using a fused prompt:
      - `prompt = <decoded image_generation_prompt> + ". Motion: " + motion_prompt`

### 2) Backend: integrate VideoSup via a separate service in `RENDER_ASSEMBLE`
**Why:** `RENDER_ASSEMBLE` currently does nothing; VideoSup exists but is not wired.

**Files**
- Update: `backend/shared/config.py` (add VideoSup service settings)
- Update: `backend/worker/tasks.py` (implement real render+assemble behavior)
- Optional add: `backend/shared/schemas/assets.py` (API output schemas)
- Optional update: `backend/shared/persistence/models.py` (only if we decide we need a dedicated table; MVP can store job info in `Asset.metadata_json`)

**VideoSup service API contract (MVP)**
- `POST /jobs`
  - Request payload:
    - `project_id`, `pipeline_run_id`
    - `render_profile` (`preview|final`), `output_format` (`mp4|hls`)
    - `scenes[]`: `{scene_id, clip_url, prompt, expected_duration_ms}`
    - `voiceover_script`, `subtitle_style`
  - Response:
    - `{job_id}`
- `GET /jobs/{job_id}`
  - Response:
    - `{job_id, state: {status, progress?, error?}, outputs?: {mp4_url?, hls_master_url?}}`

**Backend render behavior**
- In `stage_render_assemble`:
  - Load scenes + “video” assets (PixVerse clip URLs) from DB.
  - Build VideoSup job payload (aligned with [media-contract.md](file:///d:/Code/TRAE-Hackathon/AI%20storytelling/VideoSup/media-contract.md)).
  - Submit job to VideoSup service.
  - Poll until `succeeded|failed` (with timeout and exponential backoff).
  - On success:
    - Create or update a project-level `Asset` row (e.g. `asset_type="final_mp4"` and/or `asset_type="hls_master"`, `scene_id=NULL`)
    - Persist `videosup_job_id` and output URLs in `metadata_json` for traceability.
  - On failure:
    - Mark pipeline run + stage run failed using existing mechanisms.

**Backend settings**
- `VIDEOSUP_BASE_URL` (e.g. `http://videosup:9010`)
- `VIDEOSUP_POLL_INTERVAL_SEC`, `VIDEOSUP_MAX_POLL_SEC`

### 3) Backend API: expose scenes/assets + final output to the Web UI
**Why:** Web cannot render progress without querying scene + asset state.

**Files**
- Update: `backend/api/main.py`
- Add: `backend/shared/schemas/scenes.py` (Scene + assets output)
- Add: `backend/shared/schemas/assets.py` (Asset output)
- Update: `backend/shared/schemas/__init__.py` exports

**Endpoints (MVP)**
- `GET /projects/{project_id}/scenes`
  - Returns scenes ordered by scene_number, including per-scene assets (image/audio/video).
- `GET /projects/{project_id}/assets`
  - Returns project-level assets including final outputs (`final_mp4`, `hls_master`).
- `GET /projects/{project_id}/result`
  - Returns a single object `{mp4_url?, hls_master_url?}` derived from project-level assets.

**CORS**
- Add CORS middleware allowing `http://localhost:5173` (Vite default) and configurable via env.

### 4) VideoSup: turn the pipeline library into a real service
**Why:** user selected “service riêng”; currently VideoSup is not a service.

**Files**
- Add: `VideoSup/worker/videosup_service/app.py` (FastAPI app)
- Add: `VideoSup/worker/videosup_service/state.py` (in-memory job registry for MVP)
- Add: `VideoSup/worker/videosup_service/models.py` (Pydantic request/response)
- Update: `VideoSup/worker/requirements.txt` (add `fastapi`, `uvicorn[standard]`, `pydantic`)
- Update: `VideoSup/worker/Dockerfile` (run uvicorn service instead of tests in CMD; keep tests runnable via separate target or compose profile)
- Update or add: `VideoSup/docker-compose.yml` (run minio + videosup service)

**Service runtime behavior**
- On `POST /jobs`:
  - Validate payload using `videosup_worker.contracts.validate_media_job_spec`.
  - Download all `clip_url` to a job work directory using existing fetcher utilities.
  - Generate a placeholder voiceover WAV locally for MVP (sine or silence) using ffmpeg, sized to total expected duration.
  - Run `Pipeline.run(...)`.
  - Store outputs (MP4/HLS) via `StorageManager` (already supports local/S3 via env).
  - Update job state as it progresses: download → normalize → compose → package → upload.
- For MVP storage:
  - Use local storage by default (`VIDEOSUP_STORAGE_BACKEND=local`)
  - Keep MinIO support via existing env vars (already present in VideoSup compose).

### 5) Web: replace demo flow with real backend-driven flow
**Why:** user selected “Kết nối API thật”.

**Files**
- Add: `web/src/lib/api.ts` (typed API client)
- Update: `web/src/App.tsx` (replace fake progress with real polling)
- Update: `web/.env.example` (document `VITE_API_BASE_URL`)

**UI behavior mapping**
- “Input” → `POST /projects`
- “Script”:
  - Option A (minimal): call `POST /projects/{id}/runs` immediately (backend generates blueprint itself)
  - Option B (more control): `GET/PUT /projects/{id}/blueprint` then start run
  - MVP picks **Option A** to minimize UI complexity, but keep a “Blueprint editor” screen that uses `/blueprint` when needed.
- “Preview”:
  - Poll `GET /projects/{id}/scenes` to display storyboard + per-scene asset URIs when available.
- “Render”:
  - Poll `GET /projects/{id}/runs/{run_id}` for stage status and `GET /projects/{id}/result` for final MP4/HLS URLs.
- “Result”:
  - Render `<video src={mp4_url}>` when ready.

### 6) Unified local development orchestration
**Why:** today each folder has its own partial compose; MVP needs a single “bring up everything” path.

**Files**
- Add: `docker-compose.yml` at repo root (or `docker-compose.dev.yml` if you want to keep existing files untouched)

**Services**
- `redis` (existing backend dependency)
- `backend-api` (uvicorn)
- `backend-worker` (celery worker)
- `videosup` (new FastAPI VideoSup service)
- `minio` (optional; enable when using S3 backend)
- `web` (vite dev server)

## Assumptions & Decisions
- PixVerse is used in a blocking “submit + poll” manner inside Celery tasks for MVP (acceptable since Celery workers are designed for long jobs).
- VideoSup service uses an in-memory job registry for MVP; if process restarts, jobs are lost (acceptable for hackathon MVP). Next step would be Redis/SQLite-backed job store.
- Audio is placeholder-generated inside VideoSup service for MVP. Real TTS integration can replace it later without changing Web/Backend APIs (because job spec already carries `voiceover_script`).

## Verification Steps
- Backend:
  - Run existing unit tests under `backend/tests/`.
  - Manual: create project → start run → poll run and ensure final assets are persisted.
- VideoSup:
  - Run `VideoSup/worker/tests/` integration tests in an environment with ffmpeg/ffprobe (or via Docker image that includes them).
  - Manual: submit a job with 2–3 public MP4 clip URLs and confirm outputs are produced.
- Web:
  - Run typecheck/lint/build.
  - Manual: complete a full flow and confirm progress + final video renders.

