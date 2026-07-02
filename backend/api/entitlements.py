"""Phase 2 — entitlements (OSS single-tier).

Entitlements derive from a team's `plan` via this in-code map (source of
truth — a map, not a table, because it has a different lifecycle; mirrors
the working-stage-taxonomy decision). Structure spec §5.3.

This is the **OSS build**: a single fixed tier. Self-hosters aren't metered,
so resource caps are unlimited (`None`), but the multi-tenant capability
flags are off — team creation and invites are disabled by entitlement and
their endpoints are never reached. The paid build overrides this map with
free/pro tiers plus the billing layer.
"""

# None = unlimited.
ENTITLEMENTS: dict[str, dict[str, object]] = {
    "free": {
        "repos": None,
        "pages": None,
        "queries_per_month": None,
        "mcp_tokens": None,
        "seats": 1,
        "can_create_teams": False,
        "can_invite": False,
    },
}

_DEFAULT_PLAN = "free"


def get_entitlements(plan: str | None) -> dict[str, object]:
    """Entitlement set for a plan; falls back to the single OSS tier."""
    return ENTITLEMENTS.get(plan or _DEFAULT_PLAN, ENTITLEMENTS[_DEFAULT_PLAN])
