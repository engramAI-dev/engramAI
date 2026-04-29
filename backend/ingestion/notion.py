"""A6 — Notion ingestion worker (basic, flat page fetch — D25).

Fetches top-level pages from a Notion workspace, parses block content
to plain text, chunks, and dispatches embedding. No recursive sub-page
or database traversal for MVP.
"""

import logging
import uuid

import httpx
from sqlalchemy import delete

from celery_app import celery
from ingestion.chunker import chunk_file
from models.chunk import Chunk
from models.database import SyncSession
from models.document import Document
from models.ingest_job import IngestJob

logger = logging.getLogger(__name__)

_NOTION_API_VERSION = "2022-06-28"
_NOTION_BASE_URL = "https://api.notion.com/v1"


def _notion_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": _NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def _fetch_all_pages(api_key: str) -> list[dict]:
    """Search for all pages in the workspace (no recursion — D25)."""
    pages: list[dict] = []
    headers = _notion_headers(api_key)
    start_cursor = None

    while True:
        body: dict = {"filter": {"property": "object", "value": "page"}, "page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = httpx.post(
            f"{_NOTION_BASE_URL}/search",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        pages.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return pages


def _fetch_block_children(page_id: str, api_key: str) -> list[dict]:
    """Fetch direct children blocks of a page (flat, not recursive — D25)."""
    blocks: list[dict] = []
    headers = _notion_headers(api_key)
    start_cursor = None

    while True:
        url = f"{_NOTION_BASE_URL}/blocks/{page_id}/children?page_size=100"
        if start_cursor:
            url += f"&start_cursor={start_cursor}"

        resp = httpx.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        blocks.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return blocks


def _extract_text_from_rich_text(rich_text_list: list[dict]) -> str:
    """Extract plain text from Notion rich_text array."""
    return "".join(item.get("plain_text", "") for item in rich_text_list)


def _blocks_to_text(blocks: list[dict]) -> tuple[str, list[tuple[int, str]]]:
    """Convert Notion blocks to plain text.

    Returns the joined text and a list of (line_index, block_id) entries
    pointing at where each non-empty block begins in the joined output.
    Citations later use this to build a `#<block-id>` anchor that jumps
    straight to the cited block in Notion's UI.
    """
    lines: list[str] = []
    block_starts: list[tuple[int, str]] = []

    def _emit(block_id: str, *new_lines: str) -> None:
        # \n\n join inserts a blank line between entries, so each new
        # entry begins at index = len(lines) * 2 in the final string's
        # line list. We track logical entry start as len(lines) and let
        # callers convert.
        if not new_lines:
            return
        block_starts.append((len(lines), block_id))
        lines.extend(new_lines)

    for block in blocks:
        btype = block.get("type", "")
        block_data = block.get(btype, {})
        bid = block.get("id", "")

        if btype in ("paragraph", "quote", "callout", "toggle"):
            text = _extract_text_from_rich_text(block_data.get("rich_text", []))
            if text:
                _emit(bid, text)

        elif btype in ("heading_1", "heading_2", "heading_3"):
            text = _extract_text_from_rich_text(block_data.get("rich_text", []))
            level = btype[-1]
            prefix = "#" * int(level)
            if text:
                _emit(bid, f"{prefix} {text}")

        elif btype == "bulleted_list_item":
            text = _extract_text_from_rich_text(block_data.get("rich_text", []))
            if text:
                _emit(bid, f"- {text}")

        elif btype == "numbered_list_item":
            text = _extract_text_from_rich_text(block_data.get("rich_text", []))
            if text:
                _emit(bid, f"1. {text}")

        elif btype == "to_do":
            text = _extract_text_from_rich_text(block_data.get("rich_text", []))
            checked = block_data.get("checked", False)
            marker = "[x]" if checked else "[ ]"
            if text:
                _emit(bid, f"- {marker} {text}")

        elif btype == "code":
            text = _extract_text_from_rich_text(block_data.get("rich_text", []))
            lang = block_data.get("language", "")
            if text:
                _emit(bid, f"```{lang}", text, "```")

        elif btype == "divider":
            _emit(bid, "---")

        # Skip unsupported types: image, embed, table, child_page, etc.

    text = "\n\n".join(lines)
    # Convert "entry index" to actual line index in the joined text.
    # Entry i starts at line i*2 because \n\n is a one-blank-line separator.
    line_to_block = [(entry_idx * 2, bid) for entry_idx, bid in block_starts]
    return text, line_to_block


def _block_id_for_line(line_to_block: list[tuple[int, str]], line: int) -> str | None:
    """Return the block id whose region covers the given 1-based line."""
    if not line_to_block:
        return None
    # line_to_block is in ascending order. Find the last entry with start <= line-1
    # (chunker uses 1-based lines, our list uses 0-based).
    target = line - 1
    matched: str | None = None
    for start, bid in line_to_block:
        if start <= target:
            matched = bid
        else:
            break
    return matched


def _get_page_title(page: dict) -> str:
    """Extract page title from Notion page object."""
    props = page.get("properties", {})
    # The title property can have different names, but "title" type is always present
    for prop in props.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return _extract_text_from_rich_text(title_parts)
    return "Untitled"


def _get_page_url(page: dict) -> str:
    """Get the Notion page URL."""
    return page.get("url", "")


def _update_job(session, job_id: uuid.UUID, **kwargs) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select
    stmt = select(IngestJob).where(IngestJob.id == job_id)
    job = session.execute(stmt).scalar_one()
    for key, value in kwargs.items():
        setattr(job, key, value)
    session.commit()


@celery.task(name="ingestion.ingest_notion_workspace", bind=True, max_retries=2)
def ingest_notion_workspace(
    self,  # type: ignore[no-untyped-def]
    job_id: str,
    notion_api_key: str,
    user_id: str,
) -> None:
    """Fetch Notion pages, chunk content, dispatch embedding."""
    jid = uuid.UUID(job_id)
    uid = uuid.UUID(user_id)

    try:
        with SyncSession() as session:
            _update_job(session, jid, status="processing", progress=0.0)

        # Fetch all pages (delete old docs after new ones are ready)
        pages = _fetch_all_pages(notion_api_key)
        total_pages = len(pages)

        with SyncSession() as session:
            _update_job(session, jid, total_documents=total_pages)

        if total_pages == 0:
            with SyncSession() as session:
                _update_job(session, jid, status="complete", progress=1.0)
            return

        # Process each page — collect new docs, then swap old for new atomically
        new_doc_ids: list[uuid.UUID] = []
        with SyncSession() as session:
            for i, page in enumerate(pages):
                page_id = page["id"]
                title = _get_page_title(page)
                url = _get_page_url(page)

                # Fetch blocks and convert to text
                try:
                    blocks = _fetch_block_children(page_id, notion_api_key)
                except httpx.HTTPStatusError:
                    logger.warning("Could not fetch blocks for page %s", page_id)
                    continue

                text, line_to_block = _blocks_to_text(blocks)
                if not text.strip():
                    continue

                # Create Document
                doc = Document(
                    id=uuid.uuid4(),
                    user_id=uid,
                    title=title,
                    source="notion",
                    url=url,
                    metadata_={"notion_page_id": page_id},
                )
                session.add(doc)
                session.flush()
                new_doc_ids.append(doc.id)

                # Chunk — treat as markdown since we converted to markdown-ish text
                chunks = chunk_file(text, f"{title}.md")
                for idx, chunk in enumerate(chunks):
                    block_id = _block_id_for_line(line_to_block, chunk.start_line)
                    chunk_meta: dict = {}
                    if block_id:
                        chunk_meta["notion_block_id"] = block_id
                    session.add(Chunk(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        content=chunk.content,
                        chunk_index=idx,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        chunk_type=chunk.chunk_type,
                        metadata_=chunk_meta,
                    ))

                # Update progress
                progress = (i + 1) / total_pages * 0.8
                if (i + 1) % 5 == 0 or (i + 1) == total_pages:
                    _update_job(session, jid, progress=progress, documents_indexed=i + 1)

            # Delete old Notion docs (swap: old removed, new added in same commit)
            session.execute(
                delete(Document).where(
                    Document.user_id == uid,
                    Document.source == "notion",
                    Document.id.notin_(new_doc_ids),
                )
            )
            session.commit()

        # Dispatch embedding task (D22)
        with SyncSession() as session:
            _update_job(session, jid, status="embedding")

        from ingestion.embeddings import embed_chunks
        embed_chunks.delay(job_id)

    except Exception as exc:
        logger.exception("Notion ingestion failed for job %s", job_id)
        with SyncSession() as session:
            _update_job(session, jid, status="failed", error_message=str(exc)[:1000])
        raise
