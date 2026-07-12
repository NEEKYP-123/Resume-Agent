"""
Admin credential service — stores an optional password override (set via the
forgot-password reset flow) and pending reset tokens. Falls back to a local
JSON file (./local_storage/admin.json) when LOCAL_MODE=true.

If no password override has ever been set, auth.py falls back to comparing
against ADMIN_PASSWORD from settings/.env, exactly as before this feature existed.
"""
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings

LOCAL_ADMIN_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "admin.json"
)

RESET_TOKEN_TTL_MINUTES = 30

_client = None


def _hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}:{digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split(":")
    return _hash_password(password, bytes.fromhex(salt_hex)) == stored


def _read_local() -> dict:
    if not os.path.exists(LOCAL_ADMIN_FILE):
        return {}
    with open(LOCAL_ADMIN_FILE, "r") as f:
        return json.load(f)


def _write_local(data: dict):
    os.makedirs(os.path.dirname(LOCAL_ADMIN_FILE), exist_ok=True)
    with open(LOCAL_ADMIN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME]["admin_auth"]


def _read_doc() -> dict:
    if settings.LOCAL_MODE:
        return _read_local()
    collection = _get_collection()
    return collection.find_one({"_id": "admin"}, {"_id": 0}) or {}


def _write_doc(data: dict):
    if settings.LOCAL_MODE:
        _write_local(data)
        return
    collection = _get_collection()
    collection.update_one({"_id": "admin"}, {"$set": data}, upsert=True)


def verify_password(password: str) -> bool:
    doc = _read_doc()
    password_hash = doc.get("password_hash")
    if password_hash:
        return _verify_password(password, password_hash)
    return password == settings.ADMIN_PASSWORD


def set_password(new_password: str):
    doc = _read_doc()
    doc["password_hash"] = _hash_password(new_password)
    doc["reset_token"] = None
    doc["reset_token_expires"] = None
    _write_doc(doc)


def create_reset_token() -> str:
    token = secrets.token_urlsafe(32)
    doc = _read_doc()
    doc["reset_token"] = token
    doc["reset_token_expires"] = (datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)).isoformat()
    _write_doc(doc)
    return token


def consume_reset_token(token: str) -> bool:
    doc = _read_doc()
    stored_token = doc.get("reset_token")
    expires_at = doc.get("reset_token_expires")
    if not stored_token or not expires_at or stored_token != token:
        return False
    if datetime.utcnow() > datetime.fromisoformat(expires_at):
        return False

    doc["reset_token"] = None
    doc["reset_token_expires"] = None
    _write_doc(doc)
    return True
