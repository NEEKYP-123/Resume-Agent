"""
Admin credential service — stores an optional password override for the
single legacy .env admin account, set via the forgot-password reset flow
(see password_reset_service.py for token handling, shared with regular users).
Falls back to a local JSON file (./local_storage/admin.json) when LOCAL_MODE=true.

If no password override has ever been set, auth.py falls back to comparing
against ADMIN_PASSWORD from settings/.env, exactly as before this feature existed.
"""
import json
import os

from app.config import settings
from app.services import security

LOCAL_ADMIN_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "admin.json"
)

_client = None


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
        return security.verify_password(password, password_hash)
    return password == settings.ADMIN_PASSWORD


def set_password(new_password: str):
    doc = _read_doc()
    doc["password_hash"] = security.hash_password(new_password)
    _write_doc(doc)
