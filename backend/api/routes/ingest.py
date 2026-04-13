from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class IngestGitHubRequest(BaseModel):
    repo_url: str


class IngestNotionRequest(BaseModel):
    workspace_id: str


class IngestStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float | None = None


@router.post("/github", response_model=IngestStatusResponse)
async def ingest_github(request: IngestGitHubRequest) -> IngestStatusResponse:
    """Trigger ingestion of a GitHub repository."""
    # TODO: Dispatch Celery task, return job ID
    return IngestStatusResponse(job_id="placeholder", status="queued")


@router.post("/notion", response_model=IngestStatusResponse)
async def ingest_notion(request: IngestNotionRequest) -> IngestStatusResponse:
    """Trigger ingestion of a Notion workspace."""
    # TODO: Dispatch Celery task, return job ID
    return IngestStatusResponse(job_id="placeholder", status="queued")


@router.get("/status/{job_id}", response_model=IngestStatusResponse)
async def get_ingest_status(job_id: str) -> IngestStatusResponse:
    """Check the status of an ingestion job."""
    # TODO: Query Celery task status
    return IngestStatusResponse(job_id=job_id, status="unknown")
