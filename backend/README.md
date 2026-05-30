# Backend (FastAPI + Celery)

## Setup
Requires Python 3.10+ (recommended: 3.12+).

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Redis (broker)

```powershell
cd backend
docker compose up -d
```

Default Redis URL: `redis://localhost:6379/0`

## Run API

```powershell
cd backend
$env:PYTHONPATH="."
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Run Worker

```powershell
cd backend
$env:PYTHONPATH="."
celery -A worker.celery_app.celery_app worker --loglevel=INFO
```
