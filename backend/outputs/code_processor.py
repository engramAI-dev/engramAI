"""B3 — Code post-processor.

Layer 1 (user-visible v1) per `docs/v1/planning/partner-b-v1-plan.md`.
Called inline by Track A's chat engine when `intent == "generate"`.
Pure function, no DB writes.

Design: `docs/v1/planning/detailed/partner-b-b3-code-processor.md`
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import replace

from chat.engine import ChatEngineResult, SourceChunk

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    from tree_sitter_languages import get_parser

_FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", re.DOTALL)
_SUPPORTED = {"python", "typescript", "javascript", "go", "rust"}
_log = logging.getLogger(__name__)


def process_code(result: ChatEngineResult) -> ChatEngineResult:
    """Rebuild `result.response_text` with header, syntax check, and citations.

    Pure: no I/O, no mutation of `result`. Returns a new `ChatEngineResult`.
    Pass-through behavior on every failure mode — never raises.
    """
    blocks = list(_FENCE_RE.finditer(result.response_text))
    if not blocks:
        _log.info("B3: no code block found, skipping")
        return result
    if len(blocks) > 1:
        _log.info("B3: %d code blocks found, processing first only", len(blocks))

    block = blocks[0]
    lang = (block.group(1) or "").lower()
    code = block.group(2)

    processed_block = _process_block(code, lang, result)
    new_text = (
        result.response_text[: block.start()]
        + processed_block
        + result.response_text[block.end() :]
    )
    return replace(result, response_text=new_text)


def _process_block(code: str, lang: str, result: ChatEngineResult) -> str:
    warning = ""
    if lang in _SUPPORTED:
        err = _syntax_check(code, lang)
        if err is not None:
            warning = f"# WARNING: syntax check failed: {err}\n"
    elif lang:
        _log.info("B3: unsupported language: %s", lang)

    header = _header(result, lang)
    footer = _footer(result.sources)
    return f"```{lang}\n{header}{warning}{code}{footer}```"


def _syntax_check(code: str, lang: str) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            parser = get_parser(lang)
        tree = parser.parse(code.encode("utf-8"))
        if tree.root_node.has_error:
            return _first_error(tree.root_node)
        return None
    except Exception as e:  # parser load failures, encoding, etc.
        return f"{type(e).__name__}: {e}"


def _first_error(node) -> str:
    if node.is_missing or node.type == "ERROR":
        line = node.start_point[0] + 1
        col = node.start_point[1] + 1
        return f"parse error at line {line}, col {col}"
    for child in node.children:
        if child.has_error:
            return _first_error(child)
    return "parse error"


def _header(result: ChatEngineResult, lang: str) -> str:
    comment = _comment_prefix(lang)
    origin, derived = _resolve_origin(result)
    file_hint = _file_hint(result.sources)
    lines = [
        f"{comment} Suggested location: {file_hint}",
        f"{comment} Source origin: {origin}",
    ]
    if derived:
        lines.append(
            f"{comment} NOTE: source-origin flag missing, derived from chunks"
        )
    return "\n".join(lines) + "\n"


def _footer(sources: list[SourceChunk]) -> str:
    if not sources:
        return ""
    # Footer uses '#' — universally readable even if lang has a different
    # comment syntax; placement after the code body keeps it out of compiler view
    # for users who copy only the code section.
    lines = ["", "# ─── Sources ───"]
    for i, s in enumerate(sources, 1):
        lines.append(f"# {i}. {s.document_title} — {s.url}")
    return "\n".join(lines) + "\n"


def _comment_prefix(lang: str) -> str:
    # Only matters for the v1-supported set; fallback '#' is fine for the
    # unsupported pass-through case (header still emitted, never executed).
    if lang in {"javascript", "typescript", "go", "rust"}:
        return "//"
    return "#"


def _resolve_origin(result: ChatEngineResult) -> tuple[str, bool]:
    flag = getattr(result, "source_origin", None)
    if flag in {"code", "docs", "mixed"}:
        return flag, False
    if not result.sources:
        return "unknown", True
    kinds = {s.source for s in result.sources}
    if kinds == {"github"}:
        return "code", True
    if kinds == {"notion"}:
        return "docs", True
    return "mixed", True


def _file_hint(sources: list[SourceChunk]) -> str:
    for s in sources:
        if s.source == "github" and s.file_path:
            return s.file_path
    return "(no suggestion)"
