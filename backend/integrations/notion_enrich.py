"""B5 — Notion enrichment (page hierarchy, freshness).

Layer 3 (v1.5) per `docs/v1/planning/partner-b-v1-plan.md`. Feeds B10's
compare view. May collapse into Partner A's ingestion at v1.5 kickoff —
ownership boundary still open.
"""

from typing import Any


async def enrich_notion_page(document_id: str) -> dict[str, Any]:
    # TODO [B5]: fetch page hierarchy + last-edited metadata for the compare view.
    raise NotImplementedError("B5 not implemented")
