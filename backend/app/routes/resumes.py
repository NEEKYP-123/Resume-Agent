import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth import get_current_admin
from app.services import gmail_service, b2_service, mongodb_service, gemini_service

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.post("/sync")
def sync_resumes(admin: str = Depends(get_current_admin)):
    """
    Pulls new resume emails from Gmail, stores files in Backblaze B2 (or local disk),
    and creates a tracking entry in MongoDB (or local JSON) for each.
    Mirrors the step a scheduled job would normally trigger.
    """
    try:
        emails = gmail_service.fetch_resume_emails()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail fetch failed: {e}")

    created = []
    for email in emails:
        for attachment in email["attachments"]:
            b2_key = b2_service.upload_resume(attachment["data"], attachment["filename"])
            record = mongodb_service.create_entry(
                sender=email["sender"],
                subject=email["subject"],
                b2_key=b2_key,
                filename=attachment["filename"],
            )
            created.append(record)
        gmail_service.mark_processed(email["message_id"])

    return {"synced": len(created), "records": created}


@router.post("/{record_id}/score")
def score_resume(record_id: str, admin: str = Depends(get_current_admin)):
    records = mongodb_service.list_all()
    record = next((r for r in records if r["id"] == record_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    file_bytes = b2_service.download_resume(record["b2_key"])
    text = gemini_service.extract_text_from_resume(file_bytes, record["filename"])

    if not text:
        raise HTTPException(status_code=422, detail="Could not extract text from resume file")

    result = gemini_service.score_resume(text)
    score = result.get("score", 0)
    status = "shortlisted" if score >= 70 else "rejected"

    mongodb_service.update_result(record_id, score, result.get("summary", ""), status)
    return {"id": record_id, "score": score, "status": status, "summary": result.get("summary")}


@router.get("")
def list_resumes(admin: str = Depends(get_current_admin)):
    return mongodb_service.list_all()


@router.get("/export/csv")
def export_csv(admin: str = Depends(get_current_admin)):
    records = mongodb_service.list_all()

    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=["id", "sender", "subject", "filename", "score", "status", "summary", "created_at"]
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
