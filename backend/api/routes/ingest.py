"""A8 — Ingestion API routes.

Dispatches Celery tasks and tracks job status via IngestJob model.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
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
    """Trigger ingestion of a Notion workspace."""
    # Look up per-user Notion token from OAuth connection.
    result = await session.execute(
        select(UserConnection.access_token).where(
            UserConnection.user_id == uuid.UUID(user.id),
            UserConnection.provider == "notion",
        )
    )
    notion_token = result.scalar_one_or_none()

    if not notion_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notion not connected — connect via OAuth in onboarding or connections page",
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

    # Dispatch Celery task with the per-user token
    from ingestion.notion import ingest_notion_workspace
    ingest_notion_workspace.delay(
        job_id=str(job_id),
        notion_api_key=notion_token,
        user_id=user.id,
    )

    return IngestStatusResponse(job_id=str(job_id), status="queued")


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
