# Deployment (Netlify + Docker backend)

This repo contains:

- `web/`: Vite + React frontend (deploy to Netlify)
- `backend/`: FastAPI API + Celery worker
- `VideoSup/worker/`: video pipeline service
- Redis + MinIO: runtime dependencies

Netlify can host the frontend only, so the “full stack” setup is:

- Frontend: Netlify
- Backend stack: a VM/container host running Docker Compose, exposed via HTTPS

## 1) Deploy the backend stack (Docker host)

### Prerequisites

- A Linux VM with a public IP (any provider)
- A domain you control (recommended) with two DNS records:
  - `api.<your-domain>` → VM public IP
  - `media.<your-domain>` → VM public IP
- Docker + Docker Compose installed on the VM

### Configure environment

On the VM, create `deploy/.env.prod` based on the example:

- Copy: `deploy/.env.prod.example` → `deploy/.env.prod`
- Set:
  - `API_DOMAIN=api.<your-domain>`
  - `MEDIA_DOMAIN=media.<your-domain>`
  - `CORS_ALLOW_ORIGINS=https://<your-site>.netlify.app` (add your custom frontend domain too if you have one)
  - `VIDEOSUP_PUBLIC_BASE_URL=https://media.<your-domain>`
  - Change `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
  - Set `PIXVERSE_API_KEY` if you run with `PROVIDERS_MODE=pixverse` (otherwise keep `mock`)

### Start services

From the repo root on the VM:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d --build
```

After this:

- API is available at `https://api.<your-domain>`
- Media (MinIO public URLs) is available at `https://media.<your-domain>`

## 2) Deploy the frontend (Netlify)

This repo includes a Netlify configuration file at the repo root ([netlify.toml](file:///d:/Computer%20Science/AI%20storytelling/netlify.toml)).

### Netlify settings

- Connect the repository to Netlify
- Build settings are picked up automatically:
  - Base directory: `web`
  - Build command: `npm run build`
  - Publish directory: `web/dist`
- Add the environment variable:
  - `VITE_API_BASE_URL = https://api.<your-domain>`

### CORS

Make sure the backend environment includes your Netlify URL in `CORS_ALLOW_ORIGINS`, for example:

- `CORS_ALLOW_ORIGINS=https://<your-site>.netlify.app,https://<your-custom-domain>`

## Notes

- If the frontend loads but API calls fail in production, it’s almost always:
  - `VITE_API_BASE_URL` is missing/incorrect, or
  - `CORS_ALLOW_ORIGINS` doesn’t include your Netlify site URL, or
  - The API is not served over HTTPS (browser blocks mixed content).
