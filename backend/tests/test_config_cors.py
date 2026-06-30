"""Tests for CORS_ORIGINS env parsing.

Pydantic-settings parses `list[str]` as JSON by default. Railway and
other env-only platforms make pasting JSON awkward, so we accept a
comma-separated string too. Default (no env set) is unchanged.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def fresh_config(monkeypatch):
    """Reload config so env-var changes take effect for each test."""

    def _load() -> object:
        import config

        importlib.reload(config)
        return config.settings

    yield _load


def test_default_origin_unchanged(monkeypatch, fresh_config):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = fresh_config()
    assert settings.cors_origins == ["http://localhost:3000"]


def test_comma_separated_string(monkeypatch, fresh_config):
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://engram-ai.io,https://www.engram-ai.io"
    )
    settings = fresh_config()
    assert settings.cors_origins == [
        "https://engram-ai.io",
        "https://www.engram-ai.io",
    ]


def test_comma_separated_with_whitespace(monkeypatch, fresh_config):
    monkeypatch.setenv("CORS_ORIGINS", " https://a.com , https://b.com ")
    settings = fresh_config()
    assert settings.cors_origins == ["https://a.com", "https://b.com"]


def test_single_origin_no_comma(monkeypatch, fresh_config):
    monkeypatch.setenv("CORS_ORIGINS", "https://engram-ai.io")
    settings = fresh_config()
    assert settings.cors_origins == ["https://engram-ai.io"]


def test_json_list_still_works(monkeypatch, fresh_config):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.com","https://b.com"]')
    settings = fresh_config()
    assert settings.cors_origins == ["https://a.com", "https://b.com"]


def test_empty_string_falls_back_to_empty(monkeypatch, fresh_config):
    monkeypatch.setenv("CORS_ORIGINS", "")
    settings = fresh_config()
    assert settings.cors_origins == []
