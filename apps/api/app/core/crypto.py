"""Fernet symmetric encryption helper for secrets at rest."""

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    """Instantiate Fernet cipher using configured ENCRYPTION_KEY."""
    key = settings.ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)


def encrypt_value(plain_text: str | None) -> str | None:
    """Encrypt a string and return base64 encoded ciphertext string."""
    if plain_text is None:
        return None
    cipher = _get_fernet()
    encrypted_bytes = cipher.encrypt(plain_text.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_value(cipher_text: str | None) -> str | None:
    """Decrypt base64 ciphertext string and return original plaintext."""
    if cipher_text is None:
        return None
    cipher = _get_fernet()
    decrypted_bytes = cipher.decrypt(cipher_text.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")


def mask_secret(secret: str | None, visible_tail: int = 4) -> str | None:
    """Mask a secret for API responses (e.g. sk-...abcd). Never returns full secret."""
    if not secret:
        return None
    if len(secret) <= visible_tail + 3:
        return "***"
    prefix = secret[:3] if secret.startswith("sk-") or secret.startswith("EA") else ""
    return f"{prefix}...{secret[-visible_tail:]}"
