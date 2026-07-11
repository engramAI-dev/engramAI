"""Phase 2 — OSS entitlements are a single fixed tier."""

from api.entitlements import ENTITLEMENTS, get_entitlements


def test_free_tier_gated_and_single_seat() -> None:
    e = get_entitlements("free")
    assert e["can_create_teams"] is False
    assert e["can_invite"] is False
    assert e["seats"] == 1
    # Multi-workspace creation is gated off in OSS; no count cap applies.
    assert e["max_workspaces"] is None


def test_unknown_or_none_plan_falls_back_to_free() -> None:
    # OSS ships only the free tier; anything else resolves to it.
    assert get_entitlements("pro") == ENTITLEMENTS["free"]
    assert get_entitlements(None) == ENTITLEMENTS["free"]
