"""Tests for Fernet encryption helper."""

import pytest
from cryptography.fernet import InvalidToken

from app.core.crypto import decrypt_value, encrypt_value, mask_secret


def test_crypto_round_trip():
    """Verify encryption and decryption recovers exact original plaintext."""
    secret = "sk-proj-supersecrettoken123456789"
    ciphertext = encrypt_value(secret)

    assert ciphertext is not None
    assert ciphertext != secret
    assert "supersecrettoken" not in ciphertext

    decrypted = decrypt_value(ciphertext)
    assert decrypted == secret


def test_crypto_different_ciphertexts():
    """Fernet includes timestamps/IVs so two encryptions of same text yield different tokens."""
    secret = "meta_app_secret_998877"
    token1 = encrypt_value(secret)
    token2 = encrypt_value(secret)

    assert token1 != token2
    assert decrypt_value(token1) == secret
    assert decrypt_value(token2) == secret


def test_crypto_none_handling():
    """None input returns None safely."""
    assert encrypt_value(None) is None
    assert decrypt_value(None) is None


def test_crypto_invalid_token_raises():
    """Invalid ciphertext raises InvalidToken."""
    with pytest.raises(InvalidToken):
        decrypt_value("not-a-valid-fernet-token")


def test_mask_secret():
    """Verify secrets are masked and never exposed in full."""
    # OpenAI style
    assert mask_secret("sk-1234567890abcdef") == "sk-...cdef"
    # Meta style
    assert mask_secret("EAABbCcDd12345678") == "EAA...5678"
    # None or short
    assert mask_secret(None) is None
    assert mask_secret("123") == "***"
