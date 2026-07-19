"""
Job postings — each has its own title/description, used as the ATS-matching
target for resumes assigned to it. Open visibility: every authenticated user
(admin or recruiter) can see all job postings; only admins can create/edit/close
them (enforced in the route layer, not here).
Falls back to a local JSON file (./local_storage/job_postings.json) when LOCAL_MODE=true.
"""
import json
import os
import uuid
from datetime import datetime
from typing import List, Optional

from app.config import settings

LOCAL_JOBS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "job_postings.json"
)

_client = None


def _read_local() -> List[dict]:
    if not os.path.exists(LOCAL_JOBS_FILE):
        return []
    with open(LOCAL_JOBS_FILE, "r") as f:
        return json.load(f)


def _write_local(jobs: List[dict]):
    os.makedirs(os.path.dirname(LOCAL_JOBS_FILE), exist_ok=True)
    with open(LOCAL_JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME]["job_postings"]


def list_jobs() -> List[dict]:
    if settings.LOCAL_MODE:
        return _read_local()
    collection = _get_collection()
    return list(collection.find({}, {"_id": 0}))


def get_job(job_id: str) -> Optional[dict]:
    if settings.LOCAL_MODE:
        return next((j for j in _read_local() if j["id"] == job_id), None)
    collection = _get_collection()
    return collection.find_one({"id": job_id}, {"_id": 0})


def create_job(title: str, description: str, created_by: str) -> dict:
    job = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "status": "open",
        "created_by": created_by,
        "created_at": datetime.utcnow().isoformat(),
    }

    if settings.LOCAL_MODE:
        jobs = _read_local()
        jobs.append(job)
        _write_local(jobs)
        return job

    collection = _get_collection()
    collection.insert_one({**job})
    return job


def update_job(job_id: str, title: Optional[str] = None, description: Optional[str] = None) -> Optional[dict]:
    updates = {k: v for k, v in {"title": title, "description": description}.items() if v is not None}
    if not updates:
        return get_job(job_id)

    if settings.LOCAL_MODE:
        jobs = _read_local()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            return None
        job.update(updates)
        _write_local(jobs)
        return job

    collection = _get_collection()
    collection.update_one({"id": job_id}, {"$set": updates})
    return get_job(job_id)


def close_job(job_id: str) -> Optional[dict]:
    if settings.LOCAL_MODE:
        jobs = _read_local()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            return None
        job["status"] = "closed"
        _write_local(jobs)
        return job

    collection = _get_collection()
    collection.update_one({"id": job_id}, {"$set": {"status": "closed"}})
    return get_job(job_id)
