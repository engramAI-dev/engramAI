"""Lane 1 / A1 — context_lines padding helpers in documents route.

Pure-function unit tests against `_build_line_map` and `_pad_chunk`.
Route-level integration is covered by manual smoke against a seeded DB.
"""

from dataclasses import dataclass

from api.routes.documents import _build_line_map, _pad_chunk


@dataclass
class _FakeChunk:
    content: str
    start_line: int | None
    end_line: int | None


def test_build_line_map_indexes_each_line_by_absolute_lineno() -> None:
    chunks = [
        _FakeChunk("def a():\n    return 1", start_line=10, end_line=11),
        _FakeChunk("def b():\n    return 2", start_line=20, end_line=21),
    ]
    line_map = _build_line_map(chunks)
    assert line_map[10] == "def a():"
    assert line_map[11] == "    return 1"
    assert line_map[20] == "def b():"
    assert line_map[21] == "    return 2"
    assert 12 not in line_map  # gap between chunks preserved


def test_build_line_map_skips_chunks_without_start_line() -> None:
    chunks = [
        _FakeChunk("notion prose", start_line=None, end_line=None),
        _FakeChunk("code", start_line=5, end_line=5),
    ]
    line_map = _build_line_map(chunks)
    assert line_map == {5: "code"}


def test_pad_chunk_extends_range_and_clamps_at_one() -> None:
    chunks = [_FakeChunk("a\nb\nc\nd\ne", start_line=1, end_line=5)]
    line_map = _build_line_map(chunks)
    target = _FakeChunk("c", start_line=3, end_line=3)
    out = _pad_chunk(target, line_map, context_lines=10)
    assert out["padded_start_line"] == 1  # clamped
    assert out["padded_end_line"] == 13
    assert out["padded_content"] == "a\nb\nc\nd\ne"


def test_pad_chunk_skips_missing_lines_silently() -> None:
    line_map = {1: "alpha", 5: "epsilon"}
    target = _FakeChunk("alpha", start_line=1, end_line=1)
    out = _pad_chunk(target, line_map, context_lines=5)
    assert out["padded_start_line"] == 1
    assert out["padded_end_line"] == 6
    assert out["padded_content"] == "alpha\nepsilon"  # 2-4 missing, dropped


def test_pad_chunk_returns_nulls_for_chunks_without_line_numbers() -> None:
    target = _FakeChunk("notion prose", start_line=None, end_line=None)
    out = _pad_chunk(target, {}, context_lines=5)
    assert out["padded_content"] is None
    assert out["padded_start_line"] is None
    assert out["padded_end_line"] is None
