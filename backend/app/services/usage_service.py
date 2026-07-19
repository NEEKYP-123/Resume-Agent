"""
Gemini usage tracking — a running total of scoring calls and token counts,
visible only to admins. Not full cost/billing accounting, just volume visibility.
Falls back to a local JSON file (./local_storage/usage.json) when LOCAL_MODE=true.
"""
import json
import os

from app.config import settings

LOCAL_USAGE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "usage.json"
)

_client = None

_DEFAULTS = {"call_count": 0, "prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0}


def _read_local() -> dict:
    if not os.path.exists(LOCAL_USAGE_FILE):
        return dict(_DEFAULTS)
    with open(LOCAL_USAGE_FILE, "r") as f:
        return {**_DEFAULTS, **json.load(f)}


def _write_local(data: dict):
    os.makedirs(os.path.dirname(LOCAL_USAGE_FILE), exist_ok=True)
    with open(LOCAL_USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME]["usage"]


def record_call(prompt_tokens: int, candidates_tokens: int, total_tokens: int):
    if settings.LOCAL_MODE:
        data = _read_local()
        data["call_count"] += 1
        data["prompt_tokens"] += prompt_tokens
        data["candidates_tokens"] += candidates_tokens
        data["total_tokens"] += total_tokens
        _write_local(data)
        return

    collection = _get_collection()
    collection.update_one(
        {"_id": "usage"},
        {"$inc": {
            "call_count": 1,
            "prompt_tokens": prompt_tokens,
            "candidates_tokens": candidates_tokens,
            "total_tokens": total_tokens,
        }},
        upsert=True,
    )


def get_usage() -> dict:
    if settings.LOCAL_MODE:
        return _read_local()

    collection = _get_collection()
    doc = collection.find_one({"_id": "usage"}, {"_id": 0})
    return {**_DEFAULTS, **(doc or {})}
