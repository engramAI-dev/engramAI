"""A5 — GitHub ingestion worker.

Design: D18 (git clone --depth=1), D22 (two-task pipeline), D24 (sync Celery),
D27 (delete and re-create on re-ingestion).
"""

import logging
import os
import shutil
import subprocess
import tempfile
import uuid

from sqlalchemy import delete, select

from celery_app import celery
from ingestion.chunker import DENIED_DIRS, chunk_file, should_process_file
from models.chunk import Chunk
from models.database import SyncSession
from models.document import Document
from models.ingest_job import IngestJob

logger = logging.getLogger(__name__)


def _parse_repo_info(repo_url: str) -> tuple[str, str]:
    """Extract owner/repo from a GitHub URL."""
    # Handle https://github.com/owner/repo or https://github.com/owner/repo.git
    path = repo_url.rstrip("/").removesuffix(".git")
    parts = path.split("/")
    return parts[-2], parts[-1]


def _clone_repo(repo_url: str, github_token: str | None, dest: str) -> None:
    """Clone a repo with depth=1. Uses token for private repos."""
    if github_token:
        # Insert token into URL for authentication
        clone_url = repo_url.replace("https://", f"https://{github_token}@")
    else:
        clone_url = repo_url

    result = subprocess.run(
        ["git", "clone", "--depth=1", clone_url, dest],
        capture_output=True,
        text=True,
        timeout=300,  # 5 min max
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()}")


def _detect_default_branch(repo_dir: str) -> str:
    """Return the cloned repo's default branch name (falls back to 'main')."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_dir, "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch:
                return branch
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not detect default branch: %s", exc)
    return "main"


def _walk_files(repo_dir: str) -> list[str]:
    """Walk repo and return list of files that pass the filter (D19)."""
    files: list[str] = []
    for root, dirs, filenames in os.walk(repo_dir):
        # Prune denied directories in-place
        dirs[:] = [d for d in dirs if d not in DENIED_DIRS and not d.endswith(".egg-info")]

        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, repo_dir)
            if should_process_file(rel_path):
                files.append(full_path)
    return files


def _update_job(session, job_id: uuid.UUID, **kwargs) -> None:  # type: ignore[no-untyped-def]
    """Update an ingest job's fields."""
    stmt = select(IngestJob).where(IngestJob.id == job_id)
    job = session.execute(stmt).scalar_one()
    for key, value in kwargs.items():
        setattr(job, key, value)
    session.commit()


@celery.task(name="ingestion.ingest_github_repo", bind=True, max_retries=2)
def ingest_github_repo(
    self,  # type: ignore[no-untyped-def]
    job_id: str,
    repo_url: str,
    github_token: str | None,
    user_id: str,
    team_id: str,
) -> None:
    """Clone a GitHub repo, chunk files, and dispatch embedding."""
    jid = uuid.UUID(job_id)
    uid = uuid.UUID(user_id)
    tid = uuid.UUID(team_id)
    owner, repo_name = _parse_repo_info(repo_url)
    repo_slug = f"{owner}/{repo_name}"
    tmp_dir = None

    try:
        with SyncSession() as session:
            _update_job(session, jid, status="processing", progress=0.0)

        # D27: old docs deleted after new ones are inserted (same transaction)

        # Clone
        tmp_dir = tempfile.mkdtemp(prefix="engram_")
        repo_dir = os.path.join(tmp_dir, "repo")
        _clone_repo(repo_url, github_token, repo_dir)

        # Detect default branch (fixes hardcoded 'main' for repos using 'master' etc.)
        default_branch = _detect_default_branch(repo_dir)

        # Walk and filter files
        files = _walk_files(repo_dir)
        total_files = len(files)

        with SyncSession() as session:
            _update_job(session, jid, total_documents=total_files)

        if total_files == 0:
            with SyncSession() as session:
                _update_job(session, jid, status="complete", progress=1.0)
            return

        # Chunk each file — collect new doc IDs, delete old after insert
        new_doc_ids: list[uuid.UUID] = []
        with SyncSession() as session:
            for i, full_path in enumerate(files):
                rel_path = os.path.relpath(full_path, repo_dir)
                try:
                    content = open(full_path, encoding="utf-8", errors="ignore").read()
                except OSError:
                    logger.warning("Could not read file: %s", rel_path)
                    continue

                if not content.strip():
                    continue

                # Create Document
                doc = Document(
                    id=uuid.uuid4(),
                    user_id=uid,
                    team_id=tid,
                    title=os.path.basename(rel_path),
                    source="github",
                    repo=repo_slug,
                    file_path=rel_path,
                    url=f"https://github.com/{repo_slug}/blob/{default_branch}/{rel_path.replace(os.sep, '/')}",
                    language=_detect_language(rel_path),
                )
                session.add(doc)
                session.flush()  # get doc.id
                new_doc_ids.append(doc.id)

                # Chunk content
                chunks = chunk_file(content, rel_path)
                for idx, chunk in enumerate(chunks):
                    session.add(Chunk(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        content=chunk.content,
                        chunk_index=idx,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        chunk_type=chunk.chunk_type,
                        metadata_={"file_path": rel_path, "language": doc.language},
                    ))

                # Update progress
                progress = (i + 1) / total_files * 0.8  # 80% for chunking, 20% for embedding
                if (i + 1) % 10 == 0 or (i + 1) == total_files:
                    _update_job(session, jid, progress=progress, documents_indexed=i + 1)

            # Delete old docs for this repo (swap in same transaction)
            if new_doc_ids:
                session.execute(
                    delete(Document).where(
                        Document.team_id == tid,
                        Document.repo == repo_slug,
                        Document.id.notin_(new_doc_ids),
                    )
                )
            session.commit()

        # Dispatch embedding task (D22: two-task pipeline)
        with SyncSession() as session:
            _update_job(session, jid, status="embedding")

        from ingestion.embeddings import embed_chunks
        embed_chunks.delay(job_id)

    except Exception as exc:
        logger.exception("GitHub ingestion failed for job %s", job_id)
        with SyncSession() as session:
            _update_job(session, jid, status="failed", error_message=str(exc)[:1000])
        raise
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _detect_language(file_path: str) -> str | None:
    """Detect language from file extension."""
    ext_map = {
        ".py": "python", ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript", ".go": "go",
        ".rs": "rust", ".java": "java", ".rb": "ruby",
        ".sql": "sql", ".md": "markdown", ".yaml": "yaml",
        ".yml": "yaml", ".json": "json", ".toml": "toml",
        ".sh": "bash", ".css": "css", ".html": "html",
        ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
    }
    _, ext = os.path.splitext(file_path)
    return ext_map.get(ext.lower())
