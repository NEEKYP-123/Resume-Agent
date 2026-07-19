"""
Login rate-limiting — locks out an identifier (whatever username string was
submitted, whether or not that account actually exists, so lockout behavior
itself can't be used to enumerate valid usernames) after repeated failed
attempts. Falls back to a local JSON file (./local_storage/login_attempts.json)
when LOCAL_MODE=true.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings

MAX_ATTEMPTS = 5
ATTEMPT_WINDOW_MINUTES = 15
LOCKOUT_MINUTES = 15

LOCAL_ATTEMPTS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "login_attempts.json"
)

_client = None


def _read_local() -> dict:
    if not os.path.exists(LOCAL_ATTEMPTS_FILE):
        return {}
    with open(LOCAL_ATTEMPTS_FILE, "r") as f:
        return json.load(f)


def _write_local(data: dict):
    os.makedirs(os.path.dirname(LOCAL_ATTEMPTS_FILE), exist_ok=True)
    with open(LOCAL_ATTEMPTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME]["login_attempts"]


def _read_entry(identifier: str) -> dict:
    if settings.LOCAL_MODE:
        return _read_local().get(identifier, {})
    collection = _get_collection()
    return collection.find_one({"_id": identifier}, {"_id": 0}) or {}


def _write_entry(identifier: str, entry: dict):
    if settings.LOCAL_MODE:
        data = _read_local()
        data[identifier] = entry
        _write_local(data)
        return
    collection = _get_collection()
    collection.update_one({"_id": identifier}, {"$set": entry}, upsert=True)


def is_locked_out(identifier: str) -> Optional[int]:
    """Returns remaining lockout minutes, or None if not locked out."""
    entry = _read_entry(identifier)
    locked_until = entry.get("locked_until")
    if not locked_until:
        return None
    remaining = datetime.fromisoformat(locked_until) - datetime.utcnow()
    if remaining.total_seconds() <= 0:
        return None
    return max(1, int(remaining.total_seconds() // 60) + 1)


def record_failed_attempt(identifier: str):
    entry = _read_entry(identifier)
    first_attempt_at = entry.get("first_attempt_at")

    if first_attempt_at and datetime.utcnow() - datetime.fromisoformat(first_attempt_at) > timedelta(minutes=ATTEMPT_WINDOW_MINUTES):
        # Previous attempts have aged out — start a fresh window.
        entry = {}

    entry["count"] = entry.get("count", 0) + 1
    entry["first_attempt_at"] = entry.get("first_attempt_at") or datetime.utcnow().isoformat()

    if entry["count"] >= MAX_ATTEMPTS:
        entry["locked_until"] = (datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()

    _write_entry(identifier, entry)


def reset_attempts(identifier: str):
    _write_entry(identifier, {})
