"""Shared test fixtures for Partner B's backend test suite."""

from typing import Any

import pytest
from jose import jwt

from config import settings

_ALGORITHM = "HS256"


@pytest.fixture
def mint_jwt() -> Any:
    """Return a function that mints HS256 tokens against the current secret."""

    def _mint(claims: dict[str, Any]) -> str:
        return jwt.encode(claims, settings.secret_key, algorithm=_ALGORITHM)

    return _mint
