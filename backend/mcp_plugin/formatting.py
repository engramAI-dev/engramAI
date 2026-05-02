"""Re-exports for backwards compatibility with existing tests / callers.

The implementations now live in `mcp_shared.formatting`. New code
should import directly from `mcp_shared.formatting`.
"""

from mcp_shared.formatting import (
    format_citations,
    format_document,
    format_search_results,
)

__all__ = ["format_citations", "format_document", "format_search_results"]
