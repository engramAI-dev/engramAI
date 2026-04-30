"""LLM-facing response formatters.

Q7 decision: reshape API responses into markdown-ish text so MCP clients
don't waste context on raw JSON blobs.
"""

import re
from typing import Any

_LINE_HASH_RE = re.compile(r"#L(\d+)(?:-L(\d+))?$")

_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
}


def _language_for_path(path: str | None) -> str:
    """Map a file path to a fenced-code language hint. Empty string when unknown."""
    if not path:
        return ""
    lower = path.lower()
    for ext, lang in _LANG_BY_EXT.items():
        if lower.endswith(ext):
            return lang
    return ""


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


_VALID_INTENTS = frozenset({"explain", "generate", "question"})

_SOURCE_PREFERENCE: dict[str, tuple[str, ...]] = {
    "generate": ("github", "notion"),
    "question": ("notion", "github"),
}


def _reorder_by_intent(
    grouped: list[tuple[dict[str, Any], int]], intent: str | None
) -> list[tuple[dict[str, Any], int]]:
    """Stable reorder by preferred source for generate/question intents.

    Format-only — original relevance ordering is preserved within each
    source bucket. Retrieval scores are not modified (that's Lane 3 /
    feature-book FB-02).
    """
    pref = _SOURCE_PREFERENCE.get(intent or "")
    if not pref:
        return grouped
    rank = {src: i for i, src in enumerate(pref)}
    fallback = len(pref)
    return sorted(
        grouped,
        key=lambda pair: rank.get(pair[0].get("source") or "", fallback),
    )


def format_search_results(
    chunks: list[dict[str, Any]], intent: str | None = None
) -> str:
    if not chunks:
        return "No results found."

    grouped = _dedupe_by_document(chunks)
    grouped = _reorder_by_intent(grouped, intent)
    total = len(chunks)
    summary = f"Found {len(grouped)} document(s)"
    if total != len(grouped):
        summary += f" across {total} chunk(s)"
    if intent in _VALID_INTENTS:
        summary += f" — intent: {intent}"
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
            if source == "github":
                lang = _language_for_path(path)
                lines.append(f"```{lang}")
                lines.append(preview)
                lines.append("```")
            else:
                lines.append(preview)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_citations(chunks: list[dict[str, Any]]) -> str:
    """Locator-only rendering for the `cite` tool.

    No previews, no scores — just one line per source so an LLM can
    attach citations to an answer it already has.
    """
    if not chunks:
        return "No results found."
    grouped = _dedupe_by_document(chunks)
    lines: list[str] = []
    for chunk, _extras in grouped:
        source = chunk.get("source", "?")
        path = chunk.get("file_path") or ""
        url = chunk.get("url", "")
        line_label = _line_label(url)

        parts = [f"- **{source}**"]
        if path:
            parts.append(f"`{path}`")
        if line_label:
            parts.append(f"({line_label})")
        if url:
            parts.append(f"<{url}>")
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def _format_chunk_block(
    chunk: dict[str, Any], lang: str, source: str
) -> str:
    """Render a single chunk, preferring padded_content when present."""
    content = chunk.get("padded_content") or chunk.get("content") or ""
    start = chunk.get("padded_start_line") or chunk.get("start_line")
    end = chunk.get("padded_end_line") or chunk.get("end_line")

    range_label = ""
    if start is not None and end is not None:
        range_label = f" (L{start}-{end})" if start != end else f" (L{start})"

    if source == "github":
        return f"### chunk{range_label}\n```{lang}\n{content}\n```"
    return f"### section{range_label}\n{content}"


def format_document(doc: dict[str, Any]) -> str:
    title = doc.get("title", "(untitled)")
    source = doc.get("source", "?")
    path = doc.get("file_path") or ""
    url = doc.get("url", "")
    content = doc.get("content") or ""
    chunks = doc.get("chunks") or []

    header = f"# {title}\n\nSource: {source}"
    if path:
        header += f" · `{path}`"
    if url:
        header += f"\nURL: <{url}>"

    if content:
        body = content
    elif chunks:
        lang = _language_for_path(path)
        body = "\n\n".join(_format_chunk_block(c, lang, source) for c in chunks)
    else:
        body = ""

    return f"{header}\n\n{body}".rstrip() + "\n"
