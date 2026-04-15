"""B13 — Usage tracking middleware (request + token counts).

v1 scope: structured stdout logs only. No persistence (defer to v1.5
when billing drives a `usage_events` table).

See `docs/v1/planning/partner-b-v1-plan.md` §Layer 2.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response


async def usage_tracking_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    # TODO [B13]: emit structured stdout log {path, method, status, duration_ms,
    #             user_id (if authenticated), input_tokens, output_tokens}.
    return await call_next(request)
