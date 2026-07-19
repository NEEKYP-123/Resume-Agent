import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import get_current_user
from app.services import gmail_service, b2_service, mongodb_service, gemini_service, settings_service, job_postings_service

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


class AssignJobRequest(BaseModel):
    job_id: Optional[str] = None


class AddNoteRequest(BaseModel):
    text: str


def _filter_notes_for_viewer(records: list, current_user: dict) -> list:
    """Admin sees every note; recruiters only see notes they authored themselves."""
    if current_user["role"] == "admin":
        return records

    username = current_user["username"]
    filtered = []
    for r in records:
        r = {**r, "notes": [n for n in r.get("notes", []) if n.get("author") == username]}
        filtered.append(r)
    return filtered


def _resolve_job_description(record: dict) -> str:
    """
    Uses the specific job posting's description when the resume is assigned
    to one; otherwise falls back to the global default (for unassigned resumes).
    """
    job_id = record.get("job_id")
    if job_id:
        job = job_postings_service.get_job(job_id)
        if job:
            return job.get("description", "")
    return settings_service.get_job_description()


def _score_and_update(record: dict) -> dict:
    """
    Extracts resume text, scores it with Gemini (plus an ATS match score
    against the assigned job's description, or the global default if
    unassigned), and persists the result.
    """
    file_bytes = b2_service.download_resume(record["b2_key"])
    text = gemini_service.extract_text_from_resume(file_bytes, record["filename"])
    if not text:
        raise ValueError("Could not extract text from resume file")

    job_description = _resolve_job_description(record)
    result = gemini_service.score_resume(text, job_description=job_description)
    score = result.get("score", 0)
    status = "shortlisted" if score >= 70 else "rejected"
    ats_score = result.get("ats_score")
    ats_summary = result.get("ats_summary")

    mongodb_service.update_result(record["id"], score, result.get("summary", ""), status, ats_score, ats_summary)
    return {
        "id": record["id"], "score": score, "status": status,
        "summary": result.get("summary"), "ats_score": ats_score, "ats_summary": ats_summary,
    }


RESUME_FILE_EXTENSIONS = (".pdf", ".doc", ".docx")


@router.post("/sync")
def sync_resumes(current_user: dict = Depends(get_current_user)):
    """
    Scans the whole inbox for emails with attachments (not just pre-labeled
    ones), classifies each candidate attachment with Gemini to decide whether
    it's actually a resume, and only stores/tracks/scores the ones that are.
    Every scanned email gets labeled processed regardless, so nothing is
    reclassified on the next sync. Mirrors the step a scheduled job would
    normally trigger.
    """
    try:
        emails = gmail_service.fetch_candidate_emails()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail fetch failed: {e}")

    created = []
    for email in emails:
        for attachment in email["attachments"]:
            filename = attachment["filename"]
            if not filename.lower().endswith(RESUME_FILE_EXTENSIONS):
                continue  # not a resume-compatible file type — skip without spending a Gemini call

            text = gemini_service.extract_text_from_resume(attachment["data"], filename)
            if not text or not gemini_service.is_resume(text):
                continue  # classified as not a resume — don't store or track it

            b2_key = b2_service.upload_resume(attachment["data"], filename)
            record = mongodb_service.create_entry(
                sender=email["sender"],
                subject=email["subject"],
                b2_key=b2_key,
                filename=filename,
            )
            try:
                _score_and_update(record)
            except Exception:
                pass  # leave as "pending" — the dashboard's Score button can retry
            created.append(record)
        gmail_service.mark_processed(email["message_id"])

    return {"synced": len(created), "records": created}


@router.post("/{record_id}/score")
def score_resume(record_id: str, current_user: dict = Depends(get_current_user)):
    records = mongodb_service.list_all()
    record = next((r for r in records if r["id"] == record_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    try:
        return _score_and_update(record)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("")
def list_resumes(current_user: dict = Depends(get_current_user)):
    records = mongodb_service.list_all()
    return _filter_notes_for_viewer(records, current_user)


@router.post("/{record_id}/assign-job")
def assign_job(record_id: str, payload: AssignJobRequest, current_user: dict = Depends(get_current_user)):
    records = mongodb_service.list_all()
    record = next((r for r in records if r["id"] == record_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    mongodb_service.assign_job(record_id, payload.job_id)

    # Re-score against the new assignment immediately, so score/ats_score never
    # sit stale against whatever job this resume used to be assigned to.
    record["job_id"] = payload.job_id
    try:
        result = _score_and_update(record)
        return {"id": record_id, "job_id": payload.job_id, **result}
    except ValueError:
        # Extraction failed — assignment still succeeded, scoring just didn't run.
        return {"id": record_id, "job_id": payload.job_id}


@router.post("/{record_id}/notes")
def add_note(record_id: str, payload: AddNoteRequest, current_user: dict = Depends(get_current_user)):
    records = mongodb_service.list_all()
    if not any(r["id"] == record_id for r in records):
        raise HTTPException(status_code=404, detail="Record not found")

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Note text is required")

    note = mongodb_service.add_note(record_id, current_user["username"], payload.text.strip())
    return note


@router.get("/export/csv")
def export_csv(current_user: dict = Depends(get_current_user)):
    records = mongodb_service.list_all()

    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=[
            "id", "sender", "subject", "filename", "score", "status", "summary",
            "ats_score", "ats_summary", "created_at",
        ]
    )
    writer.writeheader()
    for r in records:
        writer.writerow({k: r.get(k, "") for k in writer.fieldnames})

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=resumes_export.csv"},
    )
