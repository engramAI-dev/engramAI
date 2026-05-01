"""Request-ID middleware — sets a per-request contextvar so every log line
emitted during the request carries the same correlation ID.

Honors an inbound `X-Request-ID` header when present (so callers / load
balancers can stitch their own traces); otherwise generates a fresh UUID4.
The ID is echoed back in the response header.

Mounted *outermost* in main.py so the contextvar is set before any other
middleware (including usage_tracking) reads it.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from logging_setup import new_request_id, request_id_var

_HEADER = "X-Request-ID"


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    incoming = request.headers.get(_HEADER)
    rid = incoming or new_request_id()
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers[_HEADER] = rid
    return response
