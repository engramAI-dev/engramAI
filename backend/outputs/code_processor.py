"""B3 — Code post-processor.

Layer 1 (user-visible v1) per `docs/v1/planning/partner-b-v1-plan.md`.
Called inline by Track A's chat engine when `intent == "generate"`.
Pure function, no DB writes.
"""


def process_code(raw: str, language: str | None = None) -> str:
    # TODO [B3]: light syntax sanity check, context comments, copy-ready formatting.
    raise NotImplementedError("B3 not implemented")
