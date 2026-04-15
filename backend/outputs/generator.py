"""B2 — Output generator service.

Layer 3 (v1.5) per `docs/v1/planning/partner-b-v1-plan.md`.

Consumes `ChatEngineResult` (defined by Track A in `backend/chat/engine.py`)
and produces a persisted `Output` row. The `intent` field on the result
picks the `output_type`.
"""

from typing import Any  # TODO [B2]: import ChatEngineResult once A11 lands.

from models.output import Output


async def generate_output(result: Any, output_type: str) -> Output:
    # TODO [B2]: branch on result.intent, format content, persist via B1 model.
    raise NotImplementedError("B2 not implemented")
