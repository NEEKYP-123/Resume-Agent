from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth import verify_login, create_access_token
from app.config import settings
from app.services import admin_service, gmail_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/login")
def login(payload: LoginRequest):
    if not verify_login(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token()
    return {"access_token": token, "token_type": "bearer"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    if payload.username != settings.ADMIN_USERNAME:
        # Don't reveal whether the username is wrong — just report as sent either way.
        return {"message": "If that username is valid, a reset link has been sent."}

    token = admin_service.create_reset_token()
    reset_link = f"{settings.FRONTEND_URL}/?reset_token={token}"

    try:
        gmail_service.send_email(
            subject="Resume Agent — password reset",
            body_text=(
                "A password reset was requested for your Resume Agent admin account.\n\n"
                f"Reset your password here (link expires in {admin_service.RESET_TOKEN_TTL_MINUTES} minutes):\n"
                f"{reset_link}\n\n"
                "If you didn't request this, you can ignore this email."
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not send reset email: {e}")

    return {"message": "If that username is valid, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    if not admin_service.consume_reset_token(payload.token):
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

    admin_service.set_password(payload.new_password)
    return {"message": "Password updated — you can log in with your new password now."}
