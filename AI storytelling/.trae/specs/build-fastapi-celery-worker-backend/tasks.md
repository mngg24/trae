# Tasks
- [x] Task 1: Initialize backend project skeleton (FastAPI + Celery + shared package).
  - [x] Create Python package layout for `api` and `worker` entrypoints sharing common modules (schemas, state machine, persistence, providers).
  - [x] Add dependency management via `requirements.txt` and dev instructions (local venv).
  - [x] Add local Redis runtime option (e.g., docker-compose) for Celery broker.

- [x] Task 2: Implement persistence layer (SQLite).
  - [x] Define DB models for projects, scenes, assets, and pipeline runs.
  - [x] Add migration strategy (lightweight migrations or Alembic) and initial schema.

- [x] Task 3: Implement state machine and orchestration primitives.
  - [x] Define canonical project states and allowed transitions.
  - [x] Implement idempotency keys for stage/run operations.

- [x] Task 4: Implement provider interfaces + mock providers.
  - [x] Define interfaces for LLM, text-to-image, image-to-video, and TTS.
  - [x] Implement deterministic mock providers used by default (no external keys required).

- [x] Task 5: Implement FastAPI HTTP API.
  - [x] Endpoints: create project, get project, list projects.
  - [x] Endpoints: get/update blueprint JSON (validated).
  - [x] Endpoints: start pipeline run, fetch run status/log summary.

- [x] Task 6: Implement Celery tasks for pipeline stages.
  - [x] Stage: generate blueprint (mock LLM) → persist scenes.
  - [x] Stage: generate assets (mock image/TTS/video) → persist asset references.
  - [x] Stage: render/assemble (mock) → mark completed.
  - [x] Failure path: retries, mark FAILED with reason after exhaustion.

- [x] Task 7: Add tests and basic verification tooling.
  - [x] Unit tests for schema validation, state transitions, idempotency behavior.
  - [x] Integration test (or runnable script) that starts a project and completes an end-to-end mock pipeline run.

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 1
- Task 5 depends on Task 2, Task 3, Task 4
- Task 6 depends on Task 3, Task 4, Task 5
- Task 7 depends on Task 5, Task 6
