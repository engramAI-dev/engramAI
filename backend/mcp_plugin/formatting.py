"""LLM-facing response formatters.

Q7 decision: reshape API responses into markdown-ish text so MCP clients
don't waste context on raw JSON blobs.
"""

from typing import Any


def format_search_results(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "No results found."

    lines: list[str] = [f"Found {len(chunks)} result(s):", ""]
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("document_title", "(untitled)")
        source = chunk.get("source", "?")
        path = chunk.get("file_path") or ""
        url = chunk.get("url", "")
        preview = (chunk.get("content_preview") or "").strip()
        score = chunk.get("relevance_score")

        header = f"### {i}. {title}"
        if score is not None:
            header += f"  (score {score:.3f})"
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
