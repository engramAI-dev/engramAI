"""Hermetic tests for Notion ingestion helpers.

No HTTP, no Celery, no DB. Just exercises the pure functions that
convert Notion API payloads to text + line→block mappings.
"""

import httpx
import pytest

from ingestion.notion import (
    _block_id_for_line,
    _blocks_to_text,
    _extract_text_from_rich_text,
    _fetch_block_children,
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


def test_blocks_to_text_maps_lines_correctly_for_single_line_blocks() -> None:
    """Sanity check: single-line blocks land at line 0, 2, 4, ... after \\n\\n joins."""
    blocks = [
        _para("p1", "first"),
        _para("p2", "second"),
        _para("p3", "third"),
    ]
    text, mapping = _blocks_to_text(blocks)
    assert text.split("\n") == ["first", "", "second", "", "third"]
    assert mapping == [(0, "p1"), (2, "p2"), (4, "p3")]


def test_blocks_to_text_maps_lines_correctly_after_multiline_code_block() -> None:
    """Regression: multi-line code blocks must not break line indexing of later blocks.

    The earlier implementation used `entry_idx * 2`, which silently miscounted
    once any single emit produced more than one logical line of text.
    """
    blocks = [
        _para("p1", "before"),
        _code("c1", "python", "def foo():\n    return 1"),
        _para("p2", "after"),
    ]
    text, mapping = _blocks_to_text(blocks)

    text_lines = text.split("\n")
    # Each (line_idx, block_id) entry must point to the line where that block
    # actually begins in the joined output.
    for line_idx, bid in mapping:
        if bid == "p1":
            assert text_lines[line_idx] == "before"
        elif bid == "c1":
            assert text_lines[line_idx] == "```python"
        elif bid == "p2":
            assert text_lines[line_idx] == "after"


def test_blocks_to_text_does_not_inject_blank_lines_inside_code_fence() -> None:
    """Regression: code fence + body + close-fence must be contiguous markdown."""
    blocks = [_code("c1", "bash", "make deploy")]
    text, _ = _blocks_to_text(blocks)
    # The fence open, body, and fence close should be on consecutive lines.
    assert text == "```bash\nmake deploy\n```"


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


def _table(block_id: str, has_header: bool) -> dict:
    return {
        "id": block_id,
        "type": "table",
        "has_children": True,
        "table": {"table_width": 2, "has_column_header": has_header, "has_row_header": False},
    }


def _table_row(block_id: str, *cell_texts: str) -> dict:
    return {
        "id": block_id,
        "type": "table_row",
        "table_row": {
            "cells": [[{"plain_text": text}] for text in cell_texts]
        },
    }


def test_blocks_to_text_renders_table_with_header_separator() -> None:
    """A table with has_column_header should produce a markdown header separator after row 1."""
    blocks = [
        _table("t1", has_header=True),
        _table_row("r1", "Service", "Owner"),
        _table_row("r2", "auth", "alice"),
        _table_row("r3", "billing", "bob"),
    ]
    text, mapping = _blocks_to_text(blocks)
    # All rows present, on consecutive lines (no blank line between them) so
    # downstream markdown renderers don't terminate the table after row 1.
    expected_block = (
        "| Service | Owner |\n"
        "| --- | --- |\n"
        "| auth | alice |\n"
        "| billing | bob |"
    )
    assert expected_block in text
    # The parent table block doesn't appear in the mapping (it's a wrapper).
    block_ids = [bid for _, bid in mapping]
    assert "t1" not in block_ids
    # Each row got its own block id so citations can anchor on a specific row.
    assert {"r1", "r2", "r3"}.issubset(set(block_ids))


def test_blocks_to_text_table_followed_by_paragraph_inserts_blank_separator() -> None:
    """When the table ends, a following paragraph still gets a blank line above it."""
    blocks = [
        _table("t1", has_header=False),
        _table_row("r1", "a", "b"),
        _table_row("r2", "c", "d"),
        _para("p1", "After table."),
    ]
    text, _ = _blocks_to_text(blocks)
    # Rows contiguous within the table, paragraph separated by blank line.
    assert "| a | b |\n| c | d |\n\nAfter table." in text


def test_blocks_to_text_paragraph_then_table_inserts_blank_separator() -> None:
    """A table starting after a paragraph still gets a blank line above it."""
    blocks = [
        _para("p1", "Before table."),
        _table("t1", has_header=False),
        _table_row("r1", "x", "y"),
    ]
    text, _ = _blocks_to_text(blocks)
    assert "Before table.\n\n| x | y |" in text


def test_blocks_to_text_renders_headerless_table_without_separator() -> None:
    blocks = [
        _table("t1", has_header=False),
        _table_row("r1", "a", "b"),
        _table_row("r2", "c", "d"),
    ]
    text, _ = _blocks_to_text(blocks)
    assert "| a | b |" in text
    assert "| c | d |" in text
    # No separator row when there is no header.
    assert "| --- |" not in text


def test_blocks_to_text_escapes_pipe_in_cell_content() -> None:
    blocks = [
        _table("t1", has_header=False),
        _table_row("r1", "a|b", "c"),
    ]
    text, _ = _blocks_to_text(blocks)
    assert "a\\|b" in text


def test_blocks_to_text_table_followed_by_paragraph_resets_state() -> None:
    """A non-table_row block ends the table region; subsequent table_rows shouldn't reuse stale state."""
    blocks = [
        _table("t1", has_header=True),
        _table_row("r1", "h1", "h2"),
        _para("p1", "After table."),
        _table_row("r2", "stray", "row"),  # orphan row, no preceding table block
    ]
    text, _ = _blocks_to_text(blocks)
    # First table row gets header separator
    assert "| h1 | h2 |" in text
    assert text.count("| --- | --- |") == 1
    # Paragraph still renders
    assert "After table." in text
    # Orphan row still renders as a row, but with no header separator (state was reset).
    assert "| stray | row |" in text


class _FakeResponse:
    def __init__(
        self,
        payload: dict | None = None,
        status_code: int = 200,
        headers: dict | None = None,
    ) -> None:
        self._payload = payload or {}
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=None, response=self  # type: ignore[arg-type]
            )

    def json(self) -> dict:
        return self._payload


def test_notion_request_retries_on_429_and_honors_retry_after(monkeypatch) -> None:
    """A single 429 response should be retried after the Retry-After delay."""
    from ingestion import notion as notion_module

    call_log: list[tuple[str, str]] = []
    sleeps: list[float] = []

    responses = iter([
        _FakeResponse(status_code=429, headers={"Retry-After": "0.5"}),
        _FakeResponse(payload={"ok": True}, status_code=200),
    ])

    def fake_get(url: str, headers: dict, timeout: int) -> _FakeResponse:
        call_log.append(("GET", url))
        return next(responses)

    monkeypatch.setattr("ingestion.notion.httpx.get", fake_get)
    monkeypatch.setattr(notion_module.time, "sleep", lambda s: sleeps.append(s))

    resp = notion_module._notion_request("GET", "https://api.notion.com/v1/blocks/x/children", "fake-key")
    assert resp.json() == {"ok": True}
    assert len(call_log) == 2
    assert sleeps == [0.5]


def test_notion_request_gives_up_after_max_retries(monkeypatch) -> None:
    """Persistent 429s eventually raise — we shouldn't loop forever."""
    from ingestion import notion as notion_module

    call_count = {"n": 0}

    def fake_get(url: str, headers: dict, timeout: int) -> _FakeResponse:
        call_count["n"] += 1
        return _FakeResponse(status_code=429, headers={"Retry-After": "0"})

    monkeypatch.setattr("ingestion.notion.httpx.get", fake_get)
    monkeypatch.setattr(notion_module.time, "sleep", lambda s: None)
    monkeypatch.setattr(notion_module, "_RATE_LIMIT_MAX_RETRIES", 3)

    with pytest.raises(httpx.HTTPStatusError):
        notion_module._notion_request("GET", "https://api.notion.com/v1/blocks/x/children", "fake-key")
    assert call_count["n"] == 3


def test_fetch_block_children_recurses_into_nested_blocks(monkeypatch) -> None:
    """Toggle/callout content lives one level down — must not be silently lost."""
    # Page "page-1" has one toggle "tog-1"; toggle has one paragraph "p-inside".
    responses = {
        "page-1": {
            "results": [
                {
                    "id": "tog-1",
                    "type": "toggle",
                    "has_children": True,
                    "toggle": {"rich_text": [{"plain_text": "Click to expand"}]},
                }
            ],
            "has_more": False,
        },
        "tog-1": {
            "results": [
                {
                    "id": "p-inside",
                    "type": "paragraph",
                    "has_children": False,
                    "paragraph": {"rich_text": [{"plain_text": "Hidden truth."}]},
                }
            ],
            "has_more": False,
        },
    }

    def fake_get(url: str, headers: dict, timeout: int) -> _FakeResponse:
        # url shape: .../blocks/<id>/children?page_size=100[&start_cursor=...]
        prefix = "/blocks/"
        bid = url.split(prefix, 1)[1].split("/", 1)[0]
        return _FakeResponse(responses[bid])

    monkeypatch.setattr("ingestion.notion.httpx.get", fake_get)

    blocks = _fetch_block_children("page-1", "fake-key")
    block_ids = [b["id"] for b in blocks]
    # Parent appears before its descendant (DFS order).
    assert block_ids == ["tog-1", "p-inside"]


def test_fetch_block_children_does_not_recurse_into_child_pages(monkeypatch) -> None:
    """Regression: child_page blocks own a separate top-level page.

    Recursing into them would inline the child page's content under the
    parent document, duplicating the same blocks across multiple docs.
    """
    responses = {
        "parent": {
            "results": [
                {
                    "id": "p-own",
                    "type": "paragraph",
                    "has_children": False,
                    "paragraph": {"rich_text": [{"plain_text": "Parent text."}]},
                },
                {
                    "id": "child-page-1",
                    "type": "child_page",
                    "has_children": True,
                    "child_page": {"title": "Sub page"},
                },
                {
                    "id": "child-db-1",
                    "type": "child_database",
                    "has_children": True,
                    "child_database": {"title": "Sub database"},
                },
            ],
            "has_more": False,
        },
        # If recursion misbehaves and queries these, the test fails because
        # the child block IDs would appear in the returned list.
        "child-page-1": {
            "results": [
                {"id": "leaked-p", "type": "paragraph", "has_children": False,
                 "paragraph": {"rich_text": [{"plain_text": "Should not appear."}]}}
            ],
            "has_more": False,
        },
        "child-db-1": {
            "results": [
                {"id": "leaked-db-row", "type": "paragraph", "has_children": False,
                 "paragraph": {"rich_text": [{"plain_text": "Also should not appear."}]}}
            ],
            "has_more": False,
        },
    }

    def fake_get(url, headers, timeout):
        bid = url.split("/blocks/", 1)[1].split("/", 1)[0]
        return _FakeResponse(responses[bid])

    monkeypatch.setattr("ingestion.notion.httpx.get", fake_get)

    blocks = _fetch_block_children("parent", "fake-key")
    block_ids = [b["id"] for b in blocks]
    assert block_ids == ["p-own", "child-page-1", "child-db-1"]
    assert "leaked-p" not in block_ids
    assert "leaked-db-row" not in block_ids


def test_fetch_block_children_respects_max_depth(monkeypatch) -> None:
    """Pathological nesting must not recurse forever."""
    from ingestion import notion as notion_module

    # Every block has one child of itself (cycle-ish). Recursion must stop.
    def fake_get(url: str, headers: dict, timeout: int) -> _FakeResponse:
        return _FakeResponse({
            "results": [
                {"id": "self", "type": "paragraph", "has_children": True,
                 "paragraph": {"rich_text": [{"plain_text": "loop"}]}}
            ],
            "has_more": False,
        })

    monkeypatch.setattr("ingestion.notion.httpx.get", fake_get)
    monkeypatch.setattr(notion_module, "_MAX_BLOCK_DEPTH", 3)

    blocks = _fetch_block_children("root", "fake-key")
    # depth 0 (root call) yields 1, depth 1 yields 1, depth 2 yields 1, depth 3 yields 1 (no further recursion).
    # Total = 4: one block emitted at each level until depth check stops further descent.
    assert len(blocks) == 4


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
