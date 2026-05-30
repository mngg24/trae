FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY . /app/backend

ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["sh", "-lc", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
