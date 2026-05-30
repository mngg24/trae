# Automated AI Short-Form Video Generator (Backend + Worker Queue) Spec

## Why
Short-form video generation is a long-running, multi-stage pipeline that must run asynchronously without blocking user requests. This spec defines a FastAPI API service plus a decoupled Celery worker queue backend that follows the structured JSON blueprint in plan.md.

## What Changes
- Add a FastAPI API service that creates and manages “video projects” and exposes their state machine progress.
- Add a Celery + Redis worker system that executes pipeline stages asynchronously and updates project state.
- Add a persistence layer (SQLite, dev-first) to store projects, scenes, assets, and job runs durably.
- Add provider abstraction interfaces plus a built-in mock mode to run end-to-end without external AI keys.
- Add OpenAPI-defined request/response schemas that mirror the “Structured JSON Blueprint” from plan.md.

## Impact
- Affected specs: LLM structured JSON blueprint, state machine orchestration, decoupled worker queue, asset generation pipeline.
- Affected code: new backend codebase (FastAPI app, Celery worker, DB models/migrations, provider adapters, tests), plus local dev configuration for Redis.

## Approaches Considered
- **Recommended: Single repo, two processes (API + worker)**: One shared Python package; run `uvicorn` for API and `celery worker` for background tasks. Clear separation by module boundaries but minimal operational complexity.
- **Two separate repos/services**: Stronger deployment isolation, but higher overhead for shared models/schemas and local development.
- **FastAPI background tasks only**: Simplest, but insufficient for reliability, retries, and horizontal scaling of long-running jobs.

## ADDED Requirements

### Requirement: Project Lifecycle API
The system SHALL provide an HTTP API to create, read, and manage video projects and their pipeline state.

#### Scenario: Create a project
- **WHEN** a client submits a new project with `topic` and `target_duration_seconds`
- **THEN** the system creates a project in `DRAFT` state and returns a `project_id`

#### Scenario: Fetch project state
- **WHEN** a client requests an existing project by `project_id`
- **THEN** the system returns project metadata, current state, timestamps, and per-scene status summary

### Requirement: Structured Blueprint Schema
The system SHALL represent a project’s script as a strict JSON document matching the conceptual schema in plan.md.

#### Scenario: Retrieve blueprint JSON
- **WHEN** a client requests the project blueprint
- **THEN** the system returns a JSON object with `project_meta` and `scenes[]`, where each scene includes `scene_number`, `narration_script`, `image_generation_prompt`, `camera_movement_suggestion`, and `estimated_duration_seconds`

#### Scenario: Validate blueprint JSON
- **WHEN** blueprint JSON is created or updated
- **THEN** the system validates it against server-side schema rules and rejects invalid payloads with a 4xx error and validation details

### Requirement: Pipeline State Machine
The system SHALL track each project through explicit states to support asynchronous execution and recovery.

#### Scenario: State progression
- **WHEN** a pipeline run is started for a project
- **THEN** the system transitions through defined states (example: `DRAFT → SCRIPTING → SCRIPT_READY → ASSET_GENERATING → ASSETS_READY → RENDERING → COMPLETED`)

#### Scenario: Failure handling
- **WHEN** a stage fails after configured retries
- **THEN** the system transitions the project to `FAILED` with a failure reason and retains prior artifacts for inspection

### Requirement: Decoupled Celery Worker Execution
The system SHALL execute pipeline stages using Celery tasks with Redis as the broker.

#### Scenario: Start a pipeline run
- **WHEN** a client triggers “start pipeline” for a project
- **THEN** the API enqueues Celery tasks and returns immediately with a run identifier

#### Scenario: Retries and idempotency
- **WHEN** a task is retried or delivered more than once
- **THEN** the worker uses idempotency keys (per project stage/run) to avoid duplicating durable side effects

### Requirement: Provider Abstraction + Mock Mode
The system SHALL provide provider interfaces for LLM, text-to-image, image-to-video, and TTS; and SHALL include mock implementations to run end-to-end without external credentials.

#### Scenario: Run end-to-end in mock mode
- **WHEN** mock mode is enabled via configuration
- **THEN** the worker generates deterministic placeholder outputs (e.g., fake asset URLs) while still exercising the full orchestration and persistence flow

### Requirement: Persistence (SQLite, Dev-First)
The system SHALL persist projects, scenes, assets, and pipeline runs in SQLite to survive process restarts.

#### Scenario: Restart recovery
- **WHEN** the API or worker restarts
- **THEN** the system can resume reporting the latest known state from the database

## MODIFIED Requirements

### Requirement: PixVerse Integration
**Status**: Deferred in this change.

The system SHALL define an image-to-video provider interface that can support PixVerse’s asynchronous model (submit + status retrieval or webhook) in a future change, without requiring changes to orchestration state names or database schema shape.

## REMOVED Requirements
None.

