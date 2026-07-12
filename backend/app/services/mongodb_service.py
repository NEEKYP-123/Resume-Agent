"""
MongoDB Atlas service — tracks each resume: sender, B2 key, status, score, timestamp.
Falls back to a local JSON file (./local_storage/tracking.json) when LOCAL_MODE=true.
"""
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict

from app.config import settings

LOCAL_TRACKING_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "tracking.json"
)

_client = None


def _read_local() -> List[Dict]:
    if not os.path.exists(LOCAL_TRACKING_FILE):
        return []
    with open(LOCAL_TRACKING_FILE, "r") as f:
        return json.load(f)


def _write_local(records: List[Dict]):
    os.makedirs(os.path.dirname(LOCAL_TRACKING_FILE), exist_ok=True)
    with open(LOCAL_TRACKING_FILE, "w") as f:
        json.dump(records, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME][settings.MONGODB_COLLECTION_NAME]


def create_entry(sender: str, subject: str, b2_key: str, filename: str) -> Dict:
    record = {
        "id": str(uuid.uuid4()),
        "sender": sender,
        "subject": subject,
        "filename": filename,
        "b2_key": b2_key,
        "status": "pending",
        "score": None,
        "summary": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    if settings.LOCAL_MODE:
        records = _read_local()
        records.append(record)
        _write_local(records)
        return record

    collection = _get_collection()
    collection.insert_one({**record})  # insert a copy — insert_one mutates in place with an _id
    return record


def update_result(record_id: str, score: int, summary: str, status: str):
    if settings.LOCAL_MODE:
        records = _read_local()
        for r in records:
            if r["id"] == record_id:
                r["score"] = score
                r["summary"] = summary
                r["status"] = status
        _write_local(records)
        return

    collection = _get_collection()
    collection.update_one(
        {"id": record_id},
        {"$set": {"score": score, "summary": summary, "status": status}},
    )


def list_all() -> List[Dict]:
    if settings.LOCAL_MODE:
        return _read_local()

    collection = _get_collection()
    return list(collection.find({}, {"_id": 0}))
