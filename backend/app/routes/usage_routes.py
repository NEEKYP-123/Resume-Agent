from fastapi import APIRouter, Depends

from app.auth import require_admin
from app.services import usage_service

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
def get_usage(current_user: dict = Depends(require_admin)):
    return usage_service.get_usage()
