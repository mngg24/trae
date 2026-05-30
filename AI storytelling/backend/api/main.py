from fastapi import Depends, FastAPI, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.persistence import PipelineRun, PipelineStageRun, Project, get_db, get_or_create_pipeline_run
from shared.schemas import Blueprint, PipelineRunOut, PipelineRunStartResponse, ProjectCreate, ProjectOut
from worker.celery_app import celery_app


app = FastAPI(title="AI Storytelling API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = Project(topic=payload.topic, target_duration_seconds=payload.target_duration_seconds, state="DRAFT")
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectOut(
        id=project.id,
        topic=project.topic,
        target_duration_seconds=project.target_duration_seconds,
        state=project.state,
        blueprint_present=project.blueprint_json is not None,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectOut(
        id=project.id,
        topic=project.topic,
        target_duration_seconds=project.target_duration_seconds,
        state=project.state,
        blueprint_present=project.blueprint_json is not None,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    projects = db.execute(select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return [
        ProjectOut(
            id=p.id,
            topic=p.topic,
            target_duration_seconds=p.target_duration_seconds,
            state=p.state,
            blueprint_present=p.blueprint_json is not None,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@app.get("/projects/{project_id}/blueprint", response_model=Blueprint)
def get_blueprint(project_id: str, db: Session = Depends(get_db)) -> Blueprint:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.blueprint_json is None:
        raise HTTPException(status_code=404, detail="Blueprint not set")

    return Blueprint.model_validate(project.blueprint_json)


@app.put("/projects/{project_id}/blueprint", response_model=Blueprint)
def put_blueprint(project_id: str, payload: Blueprint, db: Session = Depends(get_db)) -> Blueprint:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.project_meta.topic != project.topic:
        raise HTTPException(status_code=400, detail="project_meta.topic must match project.topic")
    if payload.project_meta.target_duration_seconds != project.target_duration_seconds:
        raise HTTPException(status_code=400, detail="project_meta.target_duration_seconds must match project")

    project.blueprint_json = payload.model_dump(mode="json")
    db.commit()
    db.refresh(project)
    return Blueprint.model_validate(project.blueprint_json)


def _run_out(run: PipelineRun, stage_runs: list[PipelineStageRun]) -> PipelineRunOut:
    log_summary = [
        f"stage={sr.stage} status={sr.status}" + (f" error={sr.error_message}" if sr.error_message else "")
        for sr in stage_runs
    ]
    return PipelineRunOut(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        current_stage=run.current_stage,
        idempotency_key=run.idempotency_key,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        stage_runs=[
            {
                "id": sr.id,
                "stage": sr.stage,
                "status": sr.status,
                "created_at": sr.created_at,
                "started_at": sr.started_at,
                "finished_at": sr.finished_at,
                "error_message": sr.error_message,
            }
            for sr in stage_runs
        ],
        log_summary=log_summary,
    )


@app.post("/projects/{project_id}/runs", response_model=PipelineRunStartResponse)
def start_pipeline_run(
    project_id: str,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> PipelineRunStartResponse:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    run, created = get_or_create_pipeline_run(db, project_id=project_id, idempotency_key=idempotency_key)
    celery_app.send_task(
        "worker.kickoff_pipeline_run",
        kwargs={"project_id": project_id, "pipeline_run_id": run.id},
    )

    stage_runs = (
        db.execute(select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == run.id)).scalars().all()
    )
    run_out = _run_out(run, stage_runs)

    if created:
        response.status_code = 201

    return PipelineRunStartResponse(created=created, run=run_out)


@app.get("/projects/{project_id}/runs/{run_id}", response_model=PipelineRunOut)
def get_pipeline_run(project_id: str, run_id: str, db: Session = Depends(get_db)) -> PipelineRunOut:
    run = db.execute(
        select(PipelineRun).where(
            PipelineRun.id == run_id,
            PipelineRun.project_id == project_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    stage_runs = (
        db.execute(select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == run.id)).scalars().all()
    )
    return _run_out(run, stage_runs)


@app.get("/runs/{run_id}", response_model=PipelineRunOut)
def get_pipeline_run_by_id(run_id: str, db: Session = Depends(get_db)) -> PipelineRunOut:
    run = db.execute(select(PipelineRun).where(PipelineRun.id == run_id)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    stage_runs = (
        db.execute(select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == run.id)).scalars().all()
    )
    return _run_out(run, stage_runs)
