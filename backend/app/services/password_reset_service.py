"""
Unified password-reset tokens for both the legacy .env admin account and
signed-up users. Tokens are stored hashed (never in plaintext) and are
single-use with a short TTL. Falls back to a local JSON file
(./local_storage/password_resets.json) when LOCAL_MODE=true.
"""
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.services import security

RESET_TOKEN_TTL_MINUTES = 30

LOCAL_RESETS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "password_resets.json"
)

_client = None


def _read_local() -> dict:
    if not os.path.exists(LOCAL_RESETS_FILE):
        return {}
    with open(LOCAL_RESETS_FILE, "r") as f:
        return json.load(f)


def _write_local(data: dict):
    os.makedirs(os.path.dirname(LOCAL_RESETS_FILE), exist_ok=True)
    with open(LOCAL_RESETS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME]["password_resets"]


def create_reset_token(identity_type: str, username: str) -> str:
    """
    identity_type: "admin" | "user" — which password-store the token applies to.
    """
    token = secrets.token_urlsafe(32)
    token_hash = security.hash_token(token)
    entry = {
        "identity_type": identity_type,
        "username": username,
        "expires_at": (datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)).isoformat(),
    }

    if settings.LOCAL_MODE:
        data = _read_local()
        data[token_hash] = entry
        _write_local(data)
    else:
        collection = _get_collection()
        collection.update_one({"_id": token_hash}, {"$set": entry}, upsert=True)

    return token


def consume_reset_token(token: str) -> Optional[dict]:
    """Validates + invalidates a token in one step. Returns {identity_type, username} or None."""
    token_hash = security.hash_token(token)

    if settings.LOCAL_MODE:
        data = _read_local()
        entry = data.get(token_hash)
        if not entry:
            return None
        if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
            return None
        del data[token_hash]
        _write_local(data)
        return {"identity_type": entry["identity_type"], "username": entry["username"]}

    collection = _get_collection()
    entry = collection.find_one({"_id": token_hash})
    if not entry:
        return None
    if datetime.utcnow() > datetime.fromisoformat(entry["expires_at"]):
        return None
    collection.delete_one({"_id": token_hash})
    return {"identity_type": entry["identity_type"], "username": entry["username"]}
