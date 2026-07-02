"""Phase 1 — secret encryption at rest."""

import pytest
from cryptography.fernet import Fernet

import crypto
from config import settings


def test_roundtrip_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    ciphertext = crypto.encrypt_secret("gho_secret123")
    assert ciphertext != "gho_secret123"
    assert crypto.decrypt_secret(ciphertext) == "gho_secret123"


def test_legacy_plaintext_passthrough_on_decrypt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A row written before encryption isn't a valid Fernet token → returned as-is.
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    assert crypto.decrypt_secret("gho_legacyplaintext") == "gho_legacyplaintext"


def test_passthrough_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "")
    assert crypto.encrypt_secret("x") == "x"
    assert crypto.decrypt_secret("x") == "x"


def test_empty_value_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    assert crypto.decrypt_secret("") == ""
