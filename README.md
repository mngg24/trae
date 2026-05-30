# AI Storytelling (Web + Backend + VideoSup)

This repo is a runnable end-to-end MVP:
- **web/**: React UI that creates a project, starts the pipeline, polls progress, and plays the final MP4.
- **backend/**: FastAPI + Celery pipeline (blueprint → assets → render/assemble).
- **VideoSup/**: FFmpeg stitching/subtitles pipeline exposed as a FastAPI service.
- PixVerse (optional): used for clip generation when `PROVIDERS_MODE=hybrid`.

## Prerequisites
- Docker Desktop (recommended for a one-command run)
- PixVerse API key (only if using `PROVIDERS_MODE=hybrid`)

## Quickstart (recommended)
1) Create a `.env` in repo root (or export env vars) based on `.env.example`.
2) Start everything:

```bash
docker compose up --build
```

3) Open:
- Web UI: http://localhost:5173
- Backend health: http://localhost:8000/health
- VideoSup health: http://localhost:9010/health
- MinIO console: http://localhost:9001

## Environment variables
Minimum for hybrid PixVerse mode:
- `PROVIDERS_MODE=hybrid`
- `PIXVERSE_API_KEY=...`

Default mock mode (no external keys):
- `PROVIDERS_MODE=mock`

Optional VideoSup settings (already defaulted in compose):
- `VIDEOSUP_PUBLIC_BASE_URL` (default `http://localhost:9000`)
- `VIDEOSUP_S3_BUCKET` (default `videosup`)
- `VIDEOSUP_S3_PREFIX` (default `videosup`)

## How it works (MVP)
1) Web calls backend:
   - `POST /projects`
   - `POST /projects/{id}/runs`
2) Backend worker runs:
   - `GENERATE_BLUEPRINT` (mock LLM blueprint)
   - `GENERATE_ASSETS` (mock image/audio + PixVerse video if hybrid)
   - `RENDER_ASSEMBLE` (submit job to VideoSup service, poll, store final MP4 URL)
3) Web polls:
   - `GET /projects/{id}/scenes`
   - `GET /projects/{id}/runs/{run_id}`
   - `GET /projects/{id}/result`

