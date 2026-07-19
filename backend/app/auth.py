from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.config import settings
from app.services import admin_service, users_service

security = HTTPBearer()


def create_access_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_login(username: str, password: str) -> bool:
    if username == settings.ADMIN_USERNAME:
        return admin_service.verify_password(password)
    return users_service.verify_user_password(username, password)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Returns {"username": ..., "role": "admin"|"recruiter"}. Role is resolved
    from the DB on every request (not trusted from the JWT claim) so a
    demoted/removed user doesn't keep elevated access for the life of their token.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        username = payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

    if username == settings.ADMIN_USERNAME:
        return {"username": username, "role": "admin"}

    user = users_service.get_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    return {"username": username, "role": user.get("role", "recruiter")}


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
