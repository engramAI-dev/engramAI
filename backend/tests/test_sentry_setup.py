"""Lane5/D3 — sentry init tests.

Hermetic: monkeypatch sentry_sdk.init so we test our gate logic and the
arguments we'd pass to the SDK without actually calling out to Sentry.
"""

from typing import Any

import pytest

import sentry_setup


def test_init_sentry_no_dsn_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}

    def fake_init(**_kwargs: Any) -> None:
        called["count"] += 1

    monkeypatch.setattr("sentry_sdk.init", fake_init)
    assert sentry_setup.init_sentry("", "production") is False
    assert called["count"] == 0


def test_init_sentry_with_dsn_calls_sdk_with_expected_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_init(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("sentry_sdk.init", fake_init)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "deadbeef")

    fake_dsn = "https://public@example.invalid/1"
    assert sentry_setup.init_sentry(fake_dsn, "production") is True

    assert captured["dsn"] == fake_dsn
    assert captured["environment"] == "production"
    assert captured["release"] == "deadbeef"
    assert captured["traces_sample_rate"] == 0.1
    assert captured["profiles_sample_rate"] == 0.0
    assert captured["send_default_pii"] is False
    integration_types = {type(i).__name__ for i in captured["integrations"]}
    assert integration_types == {"FastApiIntegration", "CeleryIntegration"}


def test_init_sentry_default_release_when_no_railway_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_init(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("sentry_sdk.init", fake_init)
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)

    sentry_setup.init_sentry("https://public@example.invalid/1", "production")
    assert captured["release"] == "dev"
