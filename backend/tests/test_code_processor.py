"""B3 — code post-processor tests.

Cases mirror `docs/v1/planning/detailed/partner-b-b3-code-processor.md`.
Pure unit tests — synthesize ChatEngineResult, no HTTP, no LLM.
"""

from chat.engine import ChatEngineResult, SourceChunk
from outputs.code_processor import process_code


def _src(source: str = "github", file_path: str | None = "backend/api/middleware.py") -> SourceChunk:
    return SourceChunk(
        chunk_id="c1",
        document_id="d1",
        document_title="middleware.py",
        file_path=file_path,
        source=source,
        url="https://github.com/x/y/blob/main/backend/api/middleware.py",
        relevance_score=0.9,
        content_preview="def get_current_user(): ...",
    )


def _result(text: str, sources: list[SourceChunk] | None = None, origin: str | None = None) -> ChatEngineResult:
    return ChatEngineResult(
        response_text=text,
        sources=sources if sources is not None else [_src()],
        conversation_id="conv1",
        message_id="msg1",
        intent="generate",
        model="claude-sonnet-4",
        input_tokens=100,
        output_tokens=200,
        source_origin=origin,
    )


def test_happy_path_python_code_origin() -> None:
    text = "Here you go:\n```python\ndef f():\n    return 1\n```\nLet me know."
    out = process_code(_result(text, origin="code"))
    assert "# Suggested location: backend/api/middleware.py" in out.response_text
    assert "# Source origin: code" in out.response_text
    assert "def f():" in out.response_text
    assert "# ─── Sources ───" in out.response_text
    assert "1. middleware.py" in out.response_text
    assert out.response_text.startswith("Here you go:\n")
    assert out.response_text.endswith("\nLet me know.")
    assert "WARNING" not in out.response_text


def test_happy_path_typescript() -> None:
    text = "```typescript\nfunction f(): number { return 1; }\n```"
    out = process_code(_result(text, origin="code"))
    assert "// Source origin: code" in out.response_text
    assert "function f()" in out.response_text
    assert "WARNING" not in out.response_text


def test_happy_path_go() -> None:
    text = "```go\npackage main\nfunc main() {}\n```"
    out = process_code(_result(text, origin="code"))
    assert "// Source origin: code" in out.response_text
    assert "WARNING" not in out.response_text


def test_unsupported_language_pass_through() -> None:
    text = "```ruby\ndef f; 1; end\n```"
    out = process_code(_result(text, origin="code"))
    assert "def f; 1; end" in out.response_text
    assert "# Suggested location:" in out.response_text
    assert "# Source origin: code" in out.response_text
    assert "WARNING" not in out.response_text


def test_syntax_error_emits_warning() -> None:
    text = "```python\ndef broken(:\n    pass\n```"
    out = process_code(_result(text, origin="code"))
    assert "# WARNING: syntax check failed:" in out.response_text
    assert "def broken(:" in out.response_text


def test_no_code_block_returns_unchanged() -> None:
    text = "Just prose, no code at all."
    r = _result(text)
    out = process_code(r)
    assert out.response_text == text
    assert out is r or out.response_text == r.response_text


def test_multiple_blocks_processes_first_only() -> None:
    text = "```python\nx = 1\n```\nand\n```python\ny = 2\n```"
    out = process_code(_result(text, origin="code"))
    # First block has header injected
    assert "# Source origin: code" in out.response_text
    # Second block still present, untouched (no second header)
    assert out.response_text.count("# Source origin:") == 1
    assert "y = 2" in out.response_text


def test_missing_origin_flag_derives_and_notes() -> None:
    text = "```python\nx = 1\n```"
    out = process_code(_result(text, origin=None))  # github source → "code"
    assert "# Source origin: code" in out.response_text
    assert "# NOTE: source-origin flag missing, derived from chunks" in out.response_text


def test_empty_sources_omits_footer() -> None:
    text = "```python\nx = 1\n```"
    out = process_code(_result(text, sources=[], origin="code"))
    assert "# ─── Sources ───" not in out.response_text
    assert "# Source origin: code" in out.response_text
    assert "# Suggested location: (no suggestion)" in out.response_text


def test_prose_around_block_preserved() -> None:
    text = "Here's the code:\n```python\nx = 1\n```\nHope this helps!"
    out = process_code(_result(text, origin="code"))
    assert out.response_text.startswith("Here's the code:\n")
    assert out.response_text.endswith("\nHope this helps!")


def test_happy_path_javascript() -> None:
    text = "```javascript\nfunction f() { return 1; }\n```"
    out = process_code(_result(text, origin="code"))
    assert "// Source origin: code" in out.response_text
    assert "function f()" in out.response_text
    assert "WARNING" not in out.response_text


def test_happy_path_rust() -> None:
    text = "```rust\nfn main() {}\n```"
    out = process_code(_result(text, origin="code"))
    assert "// Source origin: code" in out.response_text
    assert "fn main()" in out.response_text
    assert "WARNING" not in out.response_text


def test_origin_docs_explicit() -> None:
    text = "```python\nx = 1\n```"
    out = process_code(_result(text, origin="docs"))
    assert "# Source origin: docs" in out.response_text
    assert "NOTE: source-origin flag missing" not in out.response_text


def test_origin_mixed_explicit() -> None:
    text = "```python\nx = 1\n```"
    out = process_code(_result(text, origin="mixed"))
    assert "# Source origin: mixed" in out.response_text


def test_origin_derived_notion_only() -> None:
    text = "```python\nx = 1\n```"
    out = process_code(_result(text, sources=[_src(source="notion", file_path=None)], origin=None))
    assert "# Source origin: docs" in out.response_text
    assert "NOTE: source-origin flag missing, derived from chunks" in out.response_text


def test_origin_derived_mixed_sources() -> None:
    text = "```python\nx = 1\n```"
    sources = [_src(source="github"), _src(source="notion", file_path=None)]
    out = process_code(_result(text, sources=sources, origin=None))
    assert "# Source origin: mixed" in out.response_text


def test_footer_lists_multiple_sources() -> None:
    text = "```python\nx = 1\n```"
    s1 = _src()
    s2 = SourceChunk(
        chunk_id="c2", document_id="d2", document_title="config.py",
        file_path="backend/config.py", source="github",
        url="https://github.com/x/y/blob/main/backend/config.py",
        relevance_score=0.7, content_preview="...",
    )
    out = process_code(_result(text, sources=[s1, s2], origin="code"))
    assert "1. middleware.py" in out.response_text
    assert "2. config.py" in out.response_text


def test_file_hint_skips_notion_and_pathless_sources() -> None:
    text = "```python\nx = 1\n```"
    notion_src = _src(source="notion", file_path=None)
    pathless_gh = _src(file_path=None)
    real_gh = SourceChunk(
        chunk_id="c3", document_id="d3", document_title="real.py",
        file_path="backend/real.py", source="github",
        url="https://github.com/x/y/blob/main/backend/real.py",
        relevance_score=0.5, content_preview="...",
    )
    out = process_code(_result(text, sources=[notion_src, pathless_gh, real_gh], origin="mixed"))
    assert "# Suggested location: backend/real.py" in out.response_text


def test_file_hint_fallback_when_no_github_with_path() -> None:
    text = "```python\nx = 1\n```"
    out = process_code(_result(text, sources=[_src(source="notion", file_path=None)], origin="docs"))
    assert "# Suggested location: (no suggestion)" in out.response_text


def test_input_result_not_mutated() -> None:
    text = "```python\nx = 1\n```\n"
    original_sources = [_src()]
    r = _result(text, sources=original_sources, origin="code")
    original_text = r.response_text
    original_sources_ref = r.sources
    out = process_code(r)
    assert r.response_text == original_text
    assert r.sources is original_sources_ref
    assert r.sources == [_src()]
    assert out is not r
    assert out.response_text != original_text
