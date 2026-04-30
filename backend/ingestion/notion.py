"""A6 — Notion ingestion worker (basic, flat page fetch — D25).

Fetches top-level pages from a Notion workspace, parses block content
to plain text, chunks, and dispatches embedding. No recursive sub-page
or database traversal for MVP.
"""

import logging
import time
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
# Notion supports arbitrary nesting; cap recursion to avoid runaway calls on
# pathological structures. 10 covers any realistic doc.
_MAX_BLOCK_DEPTH = 10

# Block types that own a separate top-level page in Notion. Their content is
# ingested independently via _fetch_all_pages, so recursing into them here
# would duplicate the same blocks under multiple parent documents.
_OPAQUE_CHILD_BLOCK_TYPES = frozenset({"child_page", "child_database"})

# Notion's published rate limit is ~3 req/s. Larger workspaces will hit 429s
# during pagination + recursive block fetching; honor Retry-After so the whole
# job doesn't fail on a single throttle.
_RATE_LIMIT_MAX_RETRIES = 5
_RATE_LIMIT_DEFAULT_BACKOFF = 1.0


def _notion_request(
    method: str,
    url: str,
    api_key: str,
    json_body: dict | None = None,
) -> httpx.Response:
    """Make a Notion API call, retrying on 429 with Retry-After backoff."""
    headers = _notion_headers(api_key)
    last_resp: httpx.Response | None = None

    for attempt in range(_RATE_LIMIT_MAX_RETRIES):
        if method == "GET":
            resp = httpx.get(url, headers=headers, timeout=30)
        else:
            resp = httpx.post(url, headers=headers, json=json_body, timeout=30)
        last_resp = resp

        if resp.status_code != 429:
            resp.raise_for_status()
            return resp

        retry_after = resp.headers.get("Retry-After")
        try:
            delay = (
                float(retry_after)
                if retry_after
                else _RATE_LIMIT_DEFAULT_BACKOFF * (2**attempt)
            )
        except ValueError:
            delay = _RATE_LIMIT_DEFAULT_BACKOFF * (2**attempt)
        logger.warning(
            "Notion 429 (attempt %d/%d), sleeping %.1fs",
            attempt + 1,
            _RATE_LIMIT_MAX_RETRIES,
            delay,
        )
        time.sleep(delay)

    # Out of retries — surface the last response as an error.
    assert last_resp is not None
    last_resp.raise_for_status()
    return last_resp


def _notion_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": _NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def _fetch_all_pages(api_key: str) -> list[dict]:
    """Search for all pages in the workspace (no recursion — D25)."""
    pages: list[dict] = []
    start_cursor = None

    while True:
        body: dict = {"filter": {"property": "object", "value": "page"}, "page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = _notion_request(
            "POST", f"{_NOTION_BASE_URL}/search", api_key, json_body=body
        )
        data = resp.json()

        pages.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return pages


def _fetch_block_children(
    page_id: str, api_key: str, depth: int = 0
) -> list[dict]:
    """Fetch direct children blocks of a page, recursively expanding any
    block that has children of its own (toggles, callouts, list items with
    sub-content, etc.) so nested text is preserved.

    Returns blocks in DFS document order: each parent is immediately followed
    by its descendants. Each block keeps its own Notion block id, so citation
    anchors point to the actual cited block regardless of nesting depth.
    """
    blocks: list[dict] = []
    start_cursor = None

    while True:
        url = f"{_NOTION_BASE_URL}/blocks/{page_id}/children?page_size=100"
        if start_cursor:
            url += f"&start_cursor={start_cursor}"

        resp = _notion_request("GET", url, api_key)
        data = resp.json()

        for block in data.get("results", []):
            blocks.append(block)
            if (
                depth < _MAX_BLOCK_DEPTH
                and block.get("has_children")
                and block.get("type") not in _OPAQUE_CHILD_BLOCK_TYPES
            ):
                child_id = block.get("id")
                if not child_id:
                    continue
                try:
                    blocks.extend(
                        _fetch_block_children(child_id, api_key, depth + 1)
                    )
                except httpx.HTTPStatusError:
                    logger.warning(
                        "Could not fetch nested blocks under %s", child_id
                    )

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
    # Build the joined output incrementally so we can vary the separator between
    # blocks: most pairs use a blank line ("\n\n"), but consecutive table_row
    # emits join with a single "\n" so markdown table rendering isn't broken by
    # blank lines between data rows.
    joined: list[str] = []  # each entry is `separator + block_text` in order
    block_starts: list[tuple[int, str]] = []  # (0-based text line of block start, block_id)
    prev_was_table_row = False

    def _emit(block_id: str, *new_lines: str, is_table_row: bool = False) -> None:
        nonlocal prev_was_table_row
        if not new_lines:
            return
        block_text = "\n".join(new_lines)

        if not joined:
            sep = ""
            text_line = 0
        elif prev_was_table_row and is_table_row:
            # Consecutive table rows — single newline keeps the markdown table contiguous.
            sep = "\n"
            so_far = "".join(joined)
            text_line = so_far.count("\n") + 1
        else:
            # Standard inter-block separator: blank line.
            sep = "\n\n"
            so_far = "".join(joined)
            text_line = so_far.count("\n") + 2

        block_starts.append((text_line, block_id))
        joined.append(sep + block_text)
        prev_was_table_row = is_table_row

    # Track whether we're inside a table region so consecutive table_row blocks
    # can be rendered as pipe-markdown with a header separator after row 1.
    table_active = False
    table_header_pending = False

    for block in blocks:
        btype = block.get("type", "")
        block_data = block.get(btype, {})
        bid = block.get("id", "")

        # A non-table_row block ends any in-progress table region.
        if table_active and btype != "table_row":
            table_active = False
            table_header_pending = False

        if btype == "table":
            # The parent table block carries metadata but no rich_text; its
            # visible content lives in child table_row blocks, which follow in
            # DFS order thanks to recursive fetching.
            table_active = True
            table_header_pending = block_data.get("has_column_header", False)
            continue

        if btype == "table_row":
            cells = block_data.get("cells", [])
            cell_texts = [
                _extract_text_from_rich_text(cell)
                .replace("|", "\\|")
                .replace("\n", " ")
                .strip()
                for cell in cells
            ]
            row_md = "| " + " | ".join(cell_texts) + " |"
            if table_header_pending and cell_texts:
                separator = "| " + " | ".join(["---"] * len(cell_texts)) + " |"
                _emit(bid, row_md, separator, is_table_row=True)
                table_header_pending = False
            else:
                _emit(bid, row_md, is_table_row=True)
            continue

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

        # Skip unsupported types: image, embed, child_page, child_database, etc.

    text = "".join(joined)
    return text, block_starts


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
