"""Lane5/D7 — Neon pooler safety: asyncpg statement cache disabled
on pooler URLs.
"""

from models.database import _async_connect_args


def test_no_special_args_for_direct_url() -> None:
    url = "postgresql+asyncpg://u:p@ep-bold-dawn.us-east-1.aws.neon.tech/db"
    assert _async_connect_args(url) == {}


def test_disable_statement_cache_on_pooler_url() -> None:
    url = "postgresql+asyncpg://u:p@ep-bold-dawn-pooler.us-east-1.aws.neon.tech/db"
    args = _async_connect_args(url)
    assert args == {"statement_cache_size": 0}


def test_pooler_detection_substring_match() -> None:
    # The substring is forgiving — any URL containing "-pooler" trips it.
    # That's intentional: simpler than parsing hostnames, and Neon's
    # pooler hostname is the only realistic match.
    url = "postgresql+asyncpg://u:p@anything-pooler-anywhere.example/db"
    assert _async_connect_args(url) == {"statement_cache_size": 0}


def test_localhost_dev_url_unaffected() -> None:
    url = "postgresql+asyncpg://engram:engram@localhost:5432/engram"
    assert _async_connect_args(url) == {}
