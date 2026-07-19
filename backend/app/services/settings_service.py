"""
App-wide settings — currently just the target job description used for ATS
matching. Falls back to a local JSON file (./local_storage/settings.json)
when LOCAL_MODE=true.
"""
import json
import os

from app.config import settings

LOCAL_SETTINGS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "settings.json"
)

_client = None


def _read_local() -> dict:
    if not os.path.exists(LOCAL_SETTINGS_FILE):
        return {}
    with open(LOCAL_SETTINGS_FILE, "r") as f:
        return json.load(f)


def _write_local(data: dict):
    os.makedirs(os.path.dirname(LOCAL_SETTINGS_FILE), exist_ok=True)
    with open(LOCAL_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME]["app_settings"]


def get_job_description() -> str:
    if settings.LOCAL_MODE:
        return _read_local().get("job_description", "")

    collection = _get_collection()
    doc = collection.find_one({"_id": "app_settings"}, {"_id": 0})
    return (doc or {}).get("job_description", "")


def set_job_description(text: str):
    if settings.LOCAL_MODE:
        data = _read_local()
        data["job_description"] = text
        _write_local(data)
        return

    collection = _get_collection()
    collection.update_one({"_id": "app_settings"}, {"$set": {"job_description": text}}, upsert=True)
