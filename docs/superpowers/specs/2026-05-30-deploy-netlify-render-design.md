## Title

Deploy AI Storytelling (Vite SPA) to Netlify, and full backend stack (FastAPI + Celery + VideoSup) to Render with Postgres.

## Context

- Frontend is a Vite React SPA that builds to `dist/` and uses an SPA redirect rule in [netlify.toml](file:///d:/Computer%20Science/AI%20storytelling/netlify.toml).
- Backend is FastAPI + Celery and depends on Redis + a shared database. Video rendering/assembly is performed by a separate FastAPI service (VideoSup) which stores outputs in S3-compatible storage (MinIO in dev).

## Goals

- Deploy the frontend to Netlify (GitHub-connected, automatic deploys).
- Deploy the backend stack to Render (Docker builds), including:
  - API service (FastAPI)
  - Worker service (Celery)
  - VideoSup service
  - Redis (broker/result backend)
  - Postgres (shared DB for API + worker)
  - S3-compatible object storage for VideoSup outputs (recommended: managed S3/R2; optional: run MinIO as a service)
- Configure production environment variables and CORS so browser calls from Netlify work.

## Non-goals

- Custom domain, TLS termination, and CDN tuning beyond the default Netlify/Render setup.
- Multi-region/high-availability architecture.
- Observability beyond provider defaults.

## Architecture

### Frontend (Netlify)

- Builds from repo root using:
  - Build command: `npm run build`
  - Publish directory: `dist`
- SPA routes are handled by:
  - Redirect `/* -> /index.html` (status 200) in [netlify.toml](file:///d:/Computer%20Science/AI%20storytelling/netlify.toml).
- Runtime configuration:
  - `VITE_API_BASE_URL` (from [web/.env.example](file:///d:/Computer%20Science/AI%20storytelling/web/.env.example)) points to the public Render API base URL.

### Backend stack (Render)

- API service:
  - Dockerfile: [backend/Dockerfile](file:///d:/Computer%20Science/AI%20storytelling/backend/Dockerfile)
  - Port: 8000
  - Health endpoint: `GET /health` in [main.py](file:///d:/Computer%20Science/AI%20storytelling/backend/api/main.py)
- Worker service:
  - Same image as API
  - Command: `celery -A worker.celery_app.celery_app worker --loglevel=INFO` (same as local compose)
- Redis:
  - Used for `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`
- Postgres:
  - Shared by API + worker via `DB_URL`
  - Replaces SQLite for production so API and worker can scale independently and share state.
- VideoSup:
  - Dockerfile: [VideoSup/worker/Dockerfile](file:///d:/Computer%20Science/AI%20storytelling/VideoSup/worker/Dockerfile)
  - Port: `PORT` env var (default 9010)
  - Stores outputs in S3-compatible storage.

## Data flow (happy path)

1. Browser UI calls API `POST /projects`.
2. UI calls API `POST /projects/{id}/runs` (kickoff).
3. API enqueues work on Celery (Redis broker).
4. Worker runs pipeline stages and persists state in Postgres.
5. For render/assemble, worker submits a job to VideoSup (`VIDEOSUP_BASE_URL`).
6. VideoSup writes results to S3-compatible storage and returns public URLs.
7. Worker records final asset URLs in Postgres; UI polls `GET /projects/{id}/result`.

## Environment variables

### Netlify (frontend)

- `VITE_API_BASE_URL` (required)
  - Example: `https://<render-api-host>`

### Render (API + worker)

Required:
- `DB_URL`
  - Render Postgres connection string (internal or external). Must be identical for API and worker.
- `REDIS_URL`
  - Render Redis connection string.
- `CELERY_BROKER_URL` (optional if equal to `REDIS_URL`)
- `CELERY_RESULT_BACKEND` (optional if equal to `REDIS_URL`)
- `CORS_ALLOW_ORIGINS`
  - Must include the Netlify site URL, e.g. `https://<site>.netlify.app` (comma-separated supported via [config.py](file:///d:/Computer%20Science/AI%20storytelling/backend/shared/config.py)).
- `VIDEOSUP_BASE_URL`
  - Internal URL of VideoSup service on Render (preferred).

Provider mode (choose one):
- `PROVIDERS_MODE=mock` (no external provider keys; demo pipeline)
- `PROVIDERS_MODE=hybrid` plus:
  - `PIXVERSE_API_KEY`
  - Optional tuning:
    - `PIXVERSE_MODEL`, `PIXVERSE_ASPECT_RATIO`, `PIXVERSE_QUALITY`, `PIXVERSE_DURATION_SEC`

Optional (VideoSup polling/render behavior, see worker code):
- `VIDEOSUP_POLL_INTERVAL_SEC`, `VIDEOSUP_MAX_POLL_SEC`
- `VIDEOSUP_OUTPUT_FORMAT` (`mp4` or `hls`)
- `VIDEOSUP_RENDER_PROFILE` (`preview` or `final`)
- `VIDEOSUP_SUBTITLE_PRESET`, `VIDEOSUP_SUBTITLE_LANGUAGE`, `VIDEOSUP_SUBTITLE_MAX_CHARS`, `VIDEOSUP_SUBTITLE_SAFE_AREA`

### Render (VideoSup)

Storage backend (recommended: managed S3/R2):
- `VIDEOSUP_STORAGE_BACKEND=s3`
- `VIDEOSUP_S3_ENDPOINT_URL` (for S3-compatible providers; omit for AWS S3 if not needed)
- `VIDEOSUP_S3_PUBLIC_BASE_URL` (public base URL used in returned media URLs)
- `VIDEOSUP_S3_BUCKET`
- `VIDEOSUP_S3_PREFIX`
- `VIDEOSUP_S3_ACCESS_KEY_ID`
- `VIDEOSUP_S3_SECRET_ACCESS_KEY`
- `VIDEOSUP_UPLOAD_MODE=sync`

Port:
- `PORT` (Render injects; ensure the service listens on it)

## Repo changes required

1. Backend Postgres support:
   - Add a Postgres driver dependency (psycopg v3) to [backend/requirements.txt](file:///d:/Computer%20Science/AI%20storytelling/backend/requirements.txt).
   - Update [database.py](file:///d:/Computer%20Science/AI%20storytelling/backend/shared/persistence/database.py) to only set `connect_args={"check_same_thread": False}` for SQLite URLs.
2. Render blueprint:
   - Add `render.yaml` defining:
     - `web` (API) service + env vars
     - `worker` service + env vars
     - `videosup` service + env vars
     - Managed Postgres + Redis attachments
   - Use Docker build for API/worker and for VideoSup.

## Deployment steps (high-level)

1. Push repo to GitHub.
2. Create Render resources from `render.yaml` (or import via dashboard).
3. Configure `CORS_ALLOW_ORIGINS` on API to include Netlify origin.
4. Deploy Netlify site from GitHub and set `VITE_API_BASE_URL` to Render API URL.
5. Validate:
   - API `/health` returns ok
   - Worker processes jobs (Celery queue drains)
   - VideoSup `/jobs` accepts requests and returns output URLs
   - Frontend can create a project and complete a pipeline run.

## Risks and mitigations

- SQLite is not safe for multi-service scaling; use Postgres in production.
- VideoSup media URLs must be publicly accessible from browsers; configure `VIDEOSUP_S3_PUBLIC_BASE_URL` accordingly.
- CORS must include the Netlify URL; otherwise browser calls fail even if API is reachable.

