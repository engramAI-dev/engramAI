"""Shared chunking utilities (A5/A6).

Design: D20 (hybrid — AST for code, heading-split for markdown, fixed-size fallback),
D21 (~500 tokens target).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# D21: ~500 tokens ≈ ~2000 chars (rough 1:4 ratio for code)
TARGET_CHUNK_CHARS = 2000
MAX_CHUNK_CHARS = 3200  # ~800 tokens — split if larger
OVERLAP_CHARS = 200  # ~50 tokens

# D19: extension allowlist
ALLOWED_EXTENSIONS: set[str] = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".md", ".mdx", ".rst", ".txt",
    ".yaml", ".yml", ".toml", ".json",
    ".sql", ".go", ".rs", ".java", ".rb",
    ".sh", ".bash", ".zsh",
    ".css", ".scss", ".html", ".xml",
    ".c", ".cpp", ".h", ".hpp",
    ".kt", ".swift", ".dart",
    ".tf", ".hcl",
    ".graphql", ".proto",
    ".env.example", ".gitignore", "Dockerfile",
    "Makefile",
}

# D19: directory denylist
DENIED_DIRS: set[str] = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".venv", "venv", "vendor", ".next", ".nuxt",
    "target", "out", ".turbo", "coverage",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "egg-info",
}

# tree-sitter language map
_TS_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}


@dataclass
class ChunkResult:
    content: str
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed, inclusive
    chunk_type: str  # "function", "class", "heading_section", "block", etc.


def should_process_file(file_path: str) -> bool:
    """Check if a file should be processed based on allowlist/denylist (D19)."""
    import os

    parts = file_path.split(os.sep)
    # Check directory denylist
    for part in parts:
        if part in DENIED_DIRS:
            return False
        if part.endswith(".egg-info"):
            return False

    # Check filename-based allows (Dockerfile, Makefile, etc.)
    basename = os.path.basename(file_path)
    if basename in ALLOWED_EXTENSIONS:
        return True

    # Check extension allowlist
    _, ext = os.path.splitext(file_path)
    return ext.lower() in ALLOWED_EXTENSIONS


def chunk_file(content: str, file_path: str) -> list[ChunkResult]:
    """Chunk a file using the hybrid strategy (D20).

    1. Try AST-aware splitting for supported code files
    2. Use heading-aware splitting for markdown
    3. Fall back to fixed-size sliding window
    """
    import os

    if not content.strip():
        return []

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    # Try AST-aware for code files
    if ext in _TS_LANG_MAP:
        try:
            chunks = _chunk_ast(content, ext)
            if chunks:
                return chunks
        except Exception:
            logger.debug("AST chunking failed for %s, falling back", file_path)

    # Heading-aware for markdown
    if ext in {".md", ".mdx", ".rst"}:
        chunks = _chunk_markdown(content)
        if chunks:
            return chunks

    # Fixed-size fallback
    return _chunk_fixed_size(content)


def _chunk_ast(content: str, ext: str) -> list[ChunkResult]:
    """Split code into AST-level chunks (functions, classes, methods)."""
    from tree_sitter import Parser
    from tree_sitter_languages import get_parser

    lang_name = _TS_LANG_MAP[ext]
    parser: Parser = get_parser(lang_name)

    tree = parser.parse(content.encode("utf-8"))

    # Node types that represent top-level or meaningful chunks
    # Varies by language, but these cover the common cases
    chunk_node_types = {
        "function_definition",       # Python
        "class_definition",          # Python
        "function_declaration",      # JS/TS/Go/C
        "class_declaration",         # JS/TS/Java
        "method_definition",         # JS/TS classes
        "arrow_function",            # JS/TS (only top-level assignments)
        "impl_item",                 # Rust
        "fn_item",                   # Rust
        "struct_item",               # Rust
        "export_statement",          # JS/TS modules
        "interface_declaration",     # TS
        "type_alias_declaration",    # TS
        "enum_declaration",          # Java/TS
    }

    lines = content.split("\n")
    chunks: list[ChunkResult] = []
    covered_lines: set[int] = set()

    # Walk top-level children of the root node
    for node in tree.root_node.children:
        if node.type in chunk_node_types:
            start_line = node.start_point[0] + 1  # 1-indexed
            end_line = node.end_point[0] + 1
            chunk_text = "\n".join(lines[start_line - 1 : end_line])

            if len(chunk_text) > MAX_CHUNK_CHARS:
                # Split large nodes with fixed-size
                sub_chunks = _chunk_fixed_size(
                    chunk_text, base_line=start_line, chunk_type=node.type,
                )
                chunks.extend(sub_chunks)
            else:
                chunks.append(ChunkResult(
                    content=chunk_text,
                    start_line=start_line,
                    end_line=end_line,
                    chunk_type=node.type,
                ))
            covered_lines.update(range(start_line, end_line + 1))

    # Collect uncovered lines (imports, module-level code, comments)
    uncovered_lines: list[int] = sorted(set(range(1, len(lines) + 1)) - covered_lines)
    if uncovered_lines:
        # Group contiguous uncovered lines into blocks
        blocks: list[list[int]] = []
        current_block: list[int] = [uncovered_lines[0]]
        for line_num in uncovered_lines[1:]:
            if line_num == current_block[-1] + 1:
                current_block.append(line_num)
            else:
                blocks.append(current_block)
                current_block = [line_num]
        blocks.append(current_block)

        for block in blocks:
            text = "\n".join(lines[block[0] - 1 : block[-1]])
            if text.strip():
                if len(text) > MAX_CHUNK_CHARS:
                    chunks.extend(_chunk_fixed_size(text, base_line=block[0], chunk_type="block"))
                else:
                    chunks.append(ChunkResult(
                        content=text,
                        start_line=block[0],
                        end_line=block[-1],
                        chunk_type="block",
                    ))

    # Sort by start line
    chunks.sort(key=lambda c: c.start_line)
    return chunks


def _chunk_markdown(content: str) -> list[ChunkResult]:
    """Split markdown by headings, then sub-split large sections."""
    lines = content.split("\n")
    sections: list[tuple[int, int]] = []  # (start, end) 1-indexed
    current_start = 1

    for i, line in enumerate(lines):
        line_num = i + 1
        if line.startswith("#") and line_num > current_start:
            sections.append((current_start, line_num - 1))
            current_start = line_num

    # Last section
    if current_start <= len(lines):
        sections.append((current_start, len(lines)))

    chunks: list[ChunkResult] = []
    for start, end in sections:
        text = "\n".join(lines[start - 1 : end])
        if not text.strip():
            continue
        if len(text) > MAX_CHUNK_CHARS:
            chunks.extend(_chunk_fixed_size(text, base_line=start, chunk_type="heading_section"))
        else:
            chunks.append(ChunkResult(
                content=text,
                start_line=start,
                end_line=end,
                chunk_type="heading_section",
            ))

    return chunks


def _chunk_fixed_size(
    content: str,
    base_line: int = 1,
    chunk_type: str = "block",
) -> list[ChunkResult]:
    """Fixed-size sliding window with overlap."""
    lines = content.split("\n")
    if not lines:
        return []

    chunks: list[ChunkResult] = []
    current_chars = 0
    chunk_start_idx = 0  # index into lines[]

    for i, line in enumerate(lines):
        current_chars += len(line) + 1  # +1 for newline

        if current_chars >= TARGET_CHUNK_CHARS or i == len(lines) - 1:
            chunk_text = "\n".join(lines[chunk_start_idx : i + 1])
            if chunk_text.strip():
                chunks.append(ChunkResult(
                    content=chunk_text,
                    start_line=base_line + chunk_start_idx,
                    end_line=base_line + i,
                    chunk_type=chunk_type,
                ))

            if i < len(lines) - 1:
                # Calculate overlap: walk back ~OVERLAP_CHARS
                overlap_chars = 0
                overlap_start = i
                while overlap_start > chunk_start_idx and overlap_chars < OVERLAP_CHARS:
                    overlap_chars += len(lines[overlap_start]) + 1
                    overlap_start -= 1
                chunk_start_idx = overlap_start + 1
                current_chars = sum(len(lines[j]) + 1 for j in range(chunk_start_idx, i + 1))

    return chunks
