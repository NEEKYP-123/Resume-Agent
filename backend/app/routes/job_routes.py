from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.auth import get_current_user, require_admin
from app.services import job_postings_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    title: str
    description: str = ""


class UpdateJobRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


@router.get("")
def list_jobs(current_user: dict = Depends(get_current_user)):
    return job_postings_service.list_jobs()


@router.post("")
def create_job(payload: CreateJobRequest, current_user: dict = Depends(require_admin)):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Job title is required")
    return job_postings_service.create_job(payload.title.strip(), payload.description, current_user["username"])


@router.put("/{job_id}")
def update_job(job_id: str, payload: UpdateJobRequest, current_user: dict = Depends(require_admin)):
    job = job_postings_service.update_job(job_id, payload.title, payload.description)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job


@router.post("/{job_id}/close")
def close_job(job_id: str, current_user: dict = Depends(require_admin)):
    job = job_postings_service.close_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job
