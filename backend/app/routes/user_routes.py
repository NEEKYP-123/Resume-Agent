from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_admin
from app.services import users_service

router = APIRouter(prefix="/api/users", tags=["users"])


class SetRoleRequest(BaseModel):
    role: str


@router.get("")
def list_users(current_user: dict = Depends(require_admin)):
    return [
        {"username": u["username"], "email": u.get("email", ""), "role": u.get("role", "recruiter")}
        for u in users_service.list_users()
    ]


@router.post("/{username}/role")
def set_user_role(username: str, payload: SetRoleRequest, current_user: dict = Depends(require_admin)):
    try:
        users_service.set_user_role(username, payload.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"username": username, "role": payload.role}


@router.delete("/{username}")
def delete_user(username: str, current_user: dict = Depends(require_admin)):
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot remove your own account")
    users_service.delete_user(username)
    return {"message": f"Removed {username}"}
