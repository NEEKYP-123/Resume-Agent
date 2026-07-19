from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_user
from app.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class JobDescriptionRequest(BaseModel):
    job_description: str


@router.get("/job-description")
def get_job_description(current_user: dict = Depends(get_current_user)):
    return {"job_description": settings_service.get_job_description()}


@router.post("/job-description")
def set_job_description(payload: JobDescriptionRequest, current_user: dict = Depends(get_current_user)):
    settings_service.set_job_description(payload.job_description)
    return {"message": "Job description saved"}
