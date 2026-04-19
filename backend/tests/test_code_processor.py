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
