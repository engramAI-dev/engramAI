"""B6a — auth middleware test stubs.

Cases mirror `docs/v1/planning/detailed/partner-b-b6a-auth-middleware.md`.
"""

import pytest


@pytest.mark.skip(reason="B6a not implemented")
async def test_valid_token_returns_current_user() -> None:
    pass


@pytest.mark.skip(reason="B6a not implemented")
async def test_missing_header_returns_401() -> None:
    pass


@pytest.mark.skip(reason="B6a not implemented")
async def test_wrong_scheme_returns_401() -> None:
    pass


@pytest.mark.skip(reason="B6a not implemented")
async def test_bad_signature_returns_401() -> None:
    pass


@pytest.mark.skip(reason="B6a not implemented")
async def test_expired_token_returns_401() -> None:
    pass


@pytest.mark.skip(reason="B6a not implemented")
async def test_missing_sub_claim_returns_401() -> None:
    pass
