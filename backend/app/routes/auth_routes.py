from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import verify_login, create_access_token, get_current_user
from app.config import settings
from app.services import (
    admin_service, gmail_service, users_service,
    login_security_service, password_reset_service,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/login")
def login(payload: LoginRequest):
    identifier = payload.username.strip().lower()

    remaining = login_security_service.is_locked_out(identifier)
    if remaining:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed attempts — try again in {remaining} minute(s)",
        )

    if not verify_login(payload.username, payload.password):
        login_security_service.record_failed_attempt(identifier)
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    login_security_service.reset_attempts(identifier)
    token = create_access_token(payload.username)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/verify")
def verify(current_user: dict = Depends(get_current_user)):
    """
    Cheap validity check the frontend calls on page load — if the token is
    missing/expired/invalid, get_current_user's dependency raises 401 before
    this body ever runs. Also returns the role so the frontend can restore
    role-aware UI on reload without a separate round-trip.
    """
    return current_user


@router.post("/signup")
def signup(payload: SignupRequest):
    if len(payload.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    try:
        users_service.create_user(payload.username.strip(), payload.password, payload.email.strip())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = create_access_token(payload.username.strip())
    return {"access_token": token, "token_type": "bearer"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    email = payload.email.strip()
    generic_response = {"message": "If that email exists, a reset link has been sent."}

    if settings.ADMIN_EMAIL and email.lower() == settings.ADMIN_EMAIL.lower():
        identity_type, username = "admin", settings.ADMIN_USERNAME
    else:
        user = users_service.get_user_by_email(email)
        if not user:
            # Don't reveal whether the email exists — report as sent either way.
            return generic_response
        identity_type, username = "user", user["username"]

    token = password_reset_service.create_reset_token(identity_type, username)
    reset_link = f"{settings.FRONTEND_URL}/?reset_token={token}"

    try:
        gmail_service.send_email(
            to_address=email,
            subject="Resume Agent — password reset",
            body_text=(
                "A password reset was requested for your Resume Agent account.\n\n"
                f"Reset your password here (link expires in {password_reset_service.RESET_TOKEN_TTL_MINUTES} minutes):\n"
                f"{reset_link}\n\n"
                "If you didn't request this, you can ignore this email."
            ),
        )
    except Exception:
        # Don't leak internal/Gmail API error details to the client.
        raise HTTPException(status_code=502, detail="Could not send reset email — please try again later")

    return generic_response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    identity = password_reset_service.consume_reset_token(payload.token)
    if not identity:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

    if identity["identity_type"] == "admin":
        admin_service.set_password(payload.new_password)
    else:
        users_service.set_user_password(identity["username"], payload.new_password)

    return {"message": "Password updated — you can log in with your new password now."}
