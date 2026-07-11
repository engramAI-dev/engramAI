"""Phase 1 — encryption at rest for secrets (GitHub OAuth token).

Fixes G9 (GH `access_token` stored plaintext). Values are encrypted with a
Fernet key from `ENCRYPTION_KEY`. Two backward-compatibility guarantees keep
this non-breaking on live data:

- **No key configured** (local dev): passthrough — store/read plaintext. A
  warning is logged once. Production sets `ENCRYPTION_KEY`.
- **Legacy plaintext rows**: `decrypt_secret` returns the value unchanged when
  it isn't a valid Fernet token, so tokens written before this landed keep
  working and migrate to ciphertext on the user's next login.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from config import settings

logger = logging.getLogger(__name__)

_warned = False


def _fernet() -> Fernet | None:
    global _warned
    key = settings.encryption_key
    if not key:
        if not _warned:
            logger.warning(
                "ENCRYPTION_KEY is not set — secrets are stored in plaintext. "
                "Set ENCRYPTION_KEY in production."
            )
            _warned = True
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Passthrough when no key is configured."""
    f = _fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(stored: str) -> str:
    """Decrypt a stored secret. Returns legacy plaintext values unchanged."""
    if not stored:
        return stored
    f = _fernet()
    if f is None:
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except (InvalidToken, ValueError):
        # Not a Fernet token — a plaintext row written before encryption.
        return stored
