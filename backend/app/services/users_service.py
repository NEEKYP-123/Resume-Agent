"""
Signed-up user accounts — a shared workspace model: every account that logs in
(the legacy .env admin, or anyone who signs up here) sees the same dashboard
and resume data, since there's only one Gmail/B2/MongoDB integration behind it.
Falls back to a local JSON file (./local_storage/users.json) when LOCAL_MODE=true.
"""
import json
import os
from typing import List, Optional

from app.config import settings
from app.services import security

LOCAL_USERS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "local_storage", "users.json"
)

_client = None


def _read_local() -> List[dict]:
    if not os.path.exists(LOCAL_USERS_FILE):
        return []
    with open(LOCAL_USERS_FILE, "r") as f:
        return json.load(f)


def _write_local(users: List[dict]):
    os.makedirs(os.path.dirname(LOCAL_USERS_FILE), exist_ok=True)
    with open(LOCAL_USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def _get_collection():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client[settings.MONGODB_DB_NAME]["users"]


def get_user(username: str) -> Optional[dict]:
    if settings.LOCAL_MODE:
        return next((u for u in _read_local() if u["username"] == username), None)
    collection = _get_collection()
    return collection.find_one({"username": username}, {"_id": 0})


def get_user_by_email(email: str) -> Optional[dict]:
    if not email:
        return None
    if settings.LOCAL_MODE:
        return next((u for u in _read_local() if u.get("email", "").lower() == email.lower()), None)
    collection = _get_collection()
    return collection.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}}, {"_id": 0})


def list_users() -> List[dict]:
    if settings.LOCAL_MODE:
        return _read_local()
    collection = _get_collection()
    return list(collection.find({}, {"_id": 0}))


def create_user(username: str, password: str, email: str = "") -> dict:
    if username == settings.ADMIN_USERNAME or get_user(username):
        raise ValueError("Username already taken")

    user = {
        "username": username,
        "email": email,
        "password_hash": security.hash_password(password),
        "role": "recruiter",
    }

    if settings.LOCAL_MODE:
        users = _read_local()
        users.append(user)
        _write_local(users)
        return user

    collection = _get_collection()
    collection.insert_one({**user})
    return user


def set_user_role(username: str, role: str):
    if role not in ("admin", "recruiter"):
        raise ValueError("Role must be 'admin' or 'recruiter'")
    if not get_user(username):
        raise ValueError("User not found")

    if settings.LOCAL_MODE:
        users = _read_local()
        for u in users:
            if u["username"] == username:
                u["role"] = role
        _write_local(users)
        return

    collection = _get_collection()
    collection.update_one({"username": username}, {"$set": {"role": role}})


def delete_user(username: str):
    if settings.LOCAL_MODE:
        users = [u for u in _read_local() if u["username"] != username]
        _write_local(users)
        return

    collection = _get_collection()
    collection.delete_one({"username": username})


def verify_user_password(username: str, password: str) -> bool:
    user = get_user(username)
    if not user:
        return False
    return security.verify_password(password, user["password_hash"])


def set_user_password(username: str, new_password: str):
    user = get_user(username)
    if not user:
        raise ValueError("User not found")
    user["password_hash"] = security.hash_password(new_password)

    if settings.LOCAL_MODE:
        users = _read_local()
        for u in users:
            if u["username"] == username:
                u["password_hash"] = user["password_hash"]
        _write_local(users)
        return

    collection = _get_collection()
    collection.update_one({"username": username}, {"$set": {"password_hash": user["password_hash"]}})
