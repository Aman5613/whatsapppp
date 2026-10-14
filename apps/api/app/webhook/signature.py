"""Meta X-Hub-Signature-256 HMAC verification."""

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_signature(payload_bytes: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Verify that incoming webhook payload matches Meta's HMAC-SHA256 signature."""
    if not signature_header or not app_secret:
        return False

    # Header format is: sha256=<hex_digest>
    if not signature_header.startswith("sha256="):
        logger.warning("Invalid signature header format: %s", signature_header)
        return False

    expected_hash = signature_header[len("sha256=") :]

    # Compute HMAC-SHA256 using business app secret
    secret_bytes = app_secret.encode("utf-8")
    computed_hash = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()

    # Constant time comparison to prevent timing attacks
    return hmac.compare_digest(computed_hash, expected_hash)
