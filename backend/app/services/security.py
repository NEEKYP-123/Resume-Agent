"""
Shared password hashing helpers, used by both admin_service.py (the single
legacy admin account) and users_service.py (signed-up accounts).
"""
import hashlib
import os
from typing import Optional


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split(":")
    return hash_password(password, bytes.fromhex(salt_hex)) == stored


def hash_token(token: str) -> str:
    """
    For high-entropy secrets (reset tokens) rather than low-entropy passwords —
    no salt needed since the token itself already has enough entropy that a
    lookup table attack isn't feasible; a plain hash still protects it at rest
    while allowing O(1) lookup by hashing the presented token.
    """
    return hashlib.sha256(token.encode()).hexdigest()
