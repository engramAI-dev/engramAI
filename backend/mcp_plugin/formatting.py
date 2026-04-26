"""LLM-facing response formatters.

Q7 decision: reshape API responses into markdown-ish text so MCP clients
don't waste context on raw JSON blobs.
"""

import re
from typing import Any

_LINE_HASH_RE = re.compile(r"#L(\d+)(?:-L(\d+))?$")


def _line_label(url: str) -> str | None:
    """Extract a display-friendly line range from a GitHub URL hash."""
    match = _LINE_HASH_RE.search(url or "")
    if not match:
        return None
    start, end = match.group(1), match.group(2)
    return f"L{start}-{end}" if end and end != start else f"L{start}"


def _dedupe_by_document(
    chunks: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], int]]:
    """Group chunks by document_id, keep the highest-scoring as the
    representative, and report how many additional chunks were collapsed.
    Falls back to chunk_id when document_id is missing so legacy callers
    still get one row per chunk.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for c in chunks:
        key = c.get("document_id") or c.get("chunk_id") or str(id(c))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)

    result: list[tuple[dict[str, Any], int]] = []
    for key in order:
        items = sorted(
            groups[key],
            key=lambda x: x.get("relevance_score") or 0,
            reverse=True,
        )
        result.append((items[0], len(items) - 1))
    result.sort(key=lambda pair: pair[0].get("relevance_score") or 0, reverse=True)
    return result


def format_search_results(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "No results found."

    grouped = _dedupe_by_document(chunks)
    total = len(chunks)
    summary = f"Found {len(grouped)} document(s)"
    if total != len(grouped):
        summary += f" across {total} chunk(s)"
    lines: list[str] = [summary + ":", ""]

    for i, (chunk, extras) in enumerate(grouped, 1):
        title = chunk.get("document_title", "(untitled)")
        source = chunk.get("source", "?")
        path = chunk.get("file_path") or ""
        url = chunk.get("url", "")
        preview = (chunk.get("content_preview") or "").strip()
        score = chunk.get("relevance_score")
        line_label = _line_label(url)

        header = f"### {i}. {title}"
        if line_label:
            header += f" ({line_label})"
        if score is not None:
            header += f"  (score {score:.3f})"
        if extras:
            header += f"  [+{extras} more chunk{'s' if extras > 1 else ''}]"
        lines.append(header)

        locator = f"{source}" + (f" · `{path}`" if path else "")
        lines.append(locator)
        if url:
            lines.append(f"<{url}>")
        if preview:
            lines.append("")
            lines.append(preview)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_document(doc: dict[str, Any]) -> str:
    title = doc.get("title", "(untitled)")
    source = doc.get("source", "?")
    path = doc.get("file_path") or ""
    url = doc.get("url", "")
    content = doc.get("content") or ""

    header = f"# {title}\n\nSource: {source}"
    if path:
        header += f" · `{path}`"
    if url:
        header += f"\nURL: <{url}>"
    return f"{header}\n\n{content}".rstrip() + "\n"
