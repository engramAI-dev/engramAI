"""A8 — Ingestion API routes.

Dispatches Celery tasks and tracks job status via IngestJob model.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware import CurrentUser, get_current_user
from models.database import get_session
from models.ingest_job import IngestJob
from models.user import User
from models.user_connection import UserConnection

router = APIRouter()


class IngestGitHubRequest(BaseModel):
    repo_url: str


class IngestNotionRequest(BaseModel):
    workspace_id: str


class IngestStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    documents_indexed: int = 0
    total_documents: int | None = None
    error: str | None = None


class JobSummary(BaseModel):
    id: str
    source: str
    source_url: str
    status: str
    progress: float
    documents_indexed: int
    total_documents: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@router.post("/github", response_model=IngestStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_github(
    request: IngestGitHubRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IngestStatusResponse:
    """Trigger ingestion of a GitHub repository."""
    # Create job record
    job_id = uuid.uuid4()
    job = IngestJob(
        id=job_id,
        user_id=uuid.UUID(user.id),
        source="github",
        source_url=request.repo_url,
        status="queued",
    )
    session.add(job)

    # Fetch the user's GitHub token for private repo access
    result = await session.execute(
        select(User.access_token).where(User.id == uuid.UUID(user.id))
    )
    github_token = result.scalar_one_or_none()

    await session.commit()

    # Dispatch Celery task
    from ingestion.github import ingest_github_repo
    ingest_github_repo.delay(
        job_id=str(job_id),
        repo_url=request.repo_url,
        github_token=github_token,
        user_id=user.id,
    )

    return IngestStatusResponse(job_id=str(job_id), status="queued")


@router.post("/notion", response_model=IngestStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_notion(
    request: IngestNotionRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IngestStatusResponse:
    """Trigger ingestion of a specific Notion workspace."""
    # Look up the per-workspace Notion token. Multiple workspaces can be
    # connected per user; the request's workspace_id picks the one.
    result = await session.execute(
        select(UserConnection.access_token).where(
            UserConnection.user_id == uuid.UUID(user.id),
            UserConnection.provider == "notion",
            UserConnection.workspace_id == request.workspace_id,
        )
    )
    notion_token = result.scalar_one_or_none()

    if not notion_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Notion workspace '{request.workspace_id}' not connected — "
                "connect via OAuth in onboarding or connections page"
            ),
        )

    job_id = uuid.uuid4()
    job = IngestJob(
        id=job_id,
        user_id=uuid.UUID(user.id),
        source="notion",
        source_url=request.workspace_id,
        status="queued",
    )
    session.add(job)
    await session.commit()

    # Dispatch Celery task — worker scopes delete-old-docs by workspace_id
    # so other workspaces' pages survive.
    from ingestion.notion import ingest_notion_workspace
    ingest_notion_workspace.delay(
        job_id=str(job_id),
        notion_api_key=notion_token,
        user_id=user.id,
        workspace_id=request.workspace_id,
    )

    return IngestStatusResponse(job_id=str(job_id), status="queued")


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    source: str | None = Query(None, description="Filter by source: github | notion"),
    include_completed: bool = Query(
        False,
        description=(
            "Include status='complete' jobs in the response. Default false to "
            "keep the connections page clean (completed jobs are already "
            "represented by indexed documents there). The jobs page passes "
            "true to surface history."
        ),
    ),
) -> list[JobSummary]:
    """List the caller's ingest jobs.

    Default: in-flight + recently failed only. Pass `?include_completed=true`
    to also receive completed jobs (used by the jobs history view).
    """
    stmt = (
        select(IngestJob)
        .where(IngestJob.user_id == uuid.UUID(user.id))
        .order_by(IngestJob.updated_at.desc())
        .limit(50)
    )
    if not include_completed:
        stmt = stmt.where(IngestJob.status != "complete")
    if source is not None:
        stmt = stmt.where(IngestJob.source == source)

    result = await session.execute(stmt)
    jobs = result.scalars().all()

    return [
        JobSummary(
            id=str(j.id),
            source=j.source,
            source_url=j.source_url,
            status=j.status,
            progress=j.progress,
            documents_indexed=j.documents_indexed,
            total_documents=j.total_documents,
            error_message=j.error_message,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in jobs
    ]


@router.get("/status/{job_id}", response_model=IngestStatusResponse)
async def get_ingest_status(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IngestStatusResponse:
    """Check the status of an ingestion job."""
    result = await session.execute(
        select(IngestJob).where(
            IngestJob.id == uuid.UUID(job_id),
            IngestJob.user_id == uuid.UUID(user.id),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return IngestStatusResponse(
        job_id=str(job.id),
        status=job.status,
        progress=job.progress,
        documents_indexed=job.documents_indexed,
        total_documents=job.total_documents,
        error=job.error_message,
    )


@router.post("/cancel/{job_id}", status_code=status.HTTP_200_OK)
async def cancel_job(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Cancel an ingestion job by marking it as failed."""
    result = await session.execute(
        select(IngestJob).where(
            IngestJob.id == uuid.UUID(job_id),
            IngestJob.user_id == uuid.UUID(user.id),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status in ("complete", "failed"):
        return {"status": job.status, "message": "Job already finished"}

    job.status = "failed"
    job.error_message = "Cancelled by user"
    await session.commit()

    # Attempt to revoke the Celery task (best-effort)
    try:
        from celery_app import celery
        celery.control.revoke(job_id, terminate=True)
    except Exception:
        pass

    return {"status": "failed", "message": "Job cancelled"}
