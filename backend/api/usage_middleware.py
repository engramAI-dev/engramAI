"""B13 — Usage tracking middleware (request + token counts).

v1 scope: structured stdout logs only. No persistence (defer to v1.5
when billing drives a `usage_events` table).

Emits one structured log entry per request via the `engram.usage` logger;
fields land alongside ts/level/request_id when JSONFormatter is active
(see `logging_setup.py`). Token counts come from `request.state.usage`
if the chat route sets them; otherwise null.

See `docs/v1/planning/partner-b-v1-plan.md` §Layer 2.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

logger = logging.getLogger("engram.usage")


async def usage_tracking_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        user = getattr(request.state, "user", None)
        usage = getattr(request.state, "usage", None) or {}
        fields: dict[str, Any] = {
            "path": request.url.path,
            "method": request.method,
            "status": status,
            "duration_ms": duration_ms,
            "user_id": getattr(user, "id", None),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        }
        logger.info("http_request", extra=fields)
