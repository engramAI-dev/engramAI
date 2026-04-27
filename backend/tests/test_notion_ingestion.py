"""Hermetic tests for Notion ingestion helpers.

No HTTP, no Celery, no DB. Just exercises the pure functions that
convert Notion API payloads to text + line→block mappings.
"""

import pytest

from ingestion.notion import (
    _block_id_for_line,
    _blocks_to_text,
    _extract_text_from_rich_text,
    _get_page_title,
    _get_page_url,
)


def _para(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": text}]},
    }


def _heading(block_id: str, level: int, text: str) -> dict:
    btype = f"heading_{level}"
    return {
        "id": block_id,
        "type": btype,
        btype: {"rich_text": [{"plain_text": text}]},
    }


def _code(block_id: str, lang: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "code",
        "code": {"rich_text": [{"plain_text": text}], "language": lang},
    }


def test_extract_text_concatenates_rich_text() -> None:
    out = _extract_text_from_rich_text(
        [{"plain_text": "Hello "}, {"plain_text": "world"}]
    )
    assert out == "Hello world"


def test_extract_text_handles_empty() -> None:
    assert _extract_text_from_rich_text([]) == ""


def test_get_page_title_finds_title_property() -> None:
    page = {
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "Deploy guide"}]}
        }
    }
    assert _get_page_title(page) == "Deploy guide"


def test_get_page_title_falls_back_to_untitled() -> None:
    assert _get_page_title({"properties": {}}) == "Untitled"


def test_get_page_url_returns_url() -> None:
    assert _get_page_url({"url": "https://notion.so/abc"}) == "https://notion.so/abc"
    assert _get_page_url({}) == ""


def test_blocks_to_text_renders_markdown_ish() -> None:
    blocks = [
        _heading("h1", 1, "Overview"),
        _para("p1", "We deploy weekly."),
        _code("c1", "bash", "make deploy"),
    ]
    text, _ = _blocks_to_text(blocks)
    assert "# Overview" in text
    assert "We deploy weekly." in text
    assert "```bash" in text
    assert "make deploy" in text


def test_blocks_to_text_skips_unsupported_types() -> None:
    blocks = [
        _para("p1", "Visible."),
        {"id": "img1", "type": "image", "image": {}},
        _para("p2", "Also visible."),
    ]
    text, mapping = _blocks_to_text(blocks)
    assert "Visible." in text
    assert "Also visible." in text
    # Image block contributed nothing to the mapping.
    block_ids = [bid for _, bid in mapping]
    assert "img1" not in block_ids
    assert "p1" in block_ids and "p2" in block_ids


def test_blocks_to_text_drops_blocks_with_empty_text() -> None:
    blocks = [
        _para("empty", ""),
        _para("p1", "Real content."),
    ]
    text, mapping = _blocks_to_text(blocks)
    assert "Real content." in text
    block_ids = [bid for _, bid in mapping]
    assert "empty" not in block_ids


def test_blocks_to_text_returns_block_starts_in_ascending_order() -> None:
    blocks = [
        _heading("h1", 2, "First"),
        _para("p1", "Body."),
        _heading("h2", 2, "Second"),
    ]
    _, mapping = _blocks_to_text(blocks)
    starts = [start for start, _ in mapping]
    assert starts == sorted(starts)


def test_block_id_for_line_returns_covering_block() -> None:
    mapping = [(0, "h1"), (4, "p1"), (10, "h2")]
    # Line 1 (1-based) → text line 0 → block h1
    assert _block_id_for_line(mapping, 1) == "h1"
    # Line 5 → text line 4 → block p1
    assert _block_id_for_line(mapping, 5) == "p1"
    # Line 12 → between p1 and h2 (inclusive on h2) → h2
    assert _block_id_for_line(mapping, 11) == "h2"
    # Line 100 (past end) → last block
    assert _block_id_for_line(mapping, 100) == "h2"


def test_block_id_for_line_returns_none_for_empty_mapping() -> None:
    assert _block_id_for_line([], 1) is None


def test_block_id_for_line_returns_none_when_line_precedes_first_block() -> None:
    # If chunker reports a chunk starting before any tracked block (shouldn't
    # happen in practice since the first block is always at index 0, but
    # defensively):
    mapping = [(5, "p1")]
    assert _block_id_for_line(mapping, 1) is None


@pytest.mark.parametrize(
    "btype, payload, expected_marker",
    [
        ("bulleted_list_item", {"rich_text": [{"plain_text": "alpha"}]}, "- alpha"),
        ("numbered_list_item", {"rich_text": [{"plain_text": "beta"}]}, "1. beta"),
        (
            "to_do",
            {"rich_text": [{"plain_text": "ship it"}], "checked": True},
            "- [x] ship it",
        ),
        (
            "to_do",
            {"rich_text": [{"plain_text": "later"}], "checked": False},
            "- [ ] later",
        ),
        ("divider", {}, "---"),
    ],
)
def test_blocks_to_text_renders_block_variants(
    btype: str, payload: dict, expected_marker: str
) -> None:
    text, _ = _blocks_to_text([{"id": "b1", "type": btype, btype: payload}])
    assert expected_marker in text
