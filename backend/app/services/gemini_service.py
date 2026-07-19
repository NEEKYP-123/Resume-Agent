"""
Gemini service — extracts resume text and asks Gemini to score/summarize it,
using the server's GEMINI_API_KEY from settings.
"""
import json
import re
from typing import Dict

import google.generativeai as genai
import pdfplumber
import io

from app.config import settings
from app.services import usage_service

RESUME_CLASSIFICATION_PROMPT = """Determine whether the document text below is a resume/CV — a
document summarizing a person's work experience, education, and skills for a job application.
Respond ONLY with a JSON object, no markdown fences, no preamble, in this exact shape:
{{"is_resume": true or false}}

Document text:
{text}
"""

SCORING_PROMPT = """You are a resume screener. Read the resume text below and respond
ONLY with a JSON object, no markdown fences, no preamble, in this exact shape:
{{"score": <integer 0-100>, "summary": "<2 sentence summary>", "top_skills": ["skill1", "skill2"]}}

Resume text:
{resume_text}
"""

SCORING_PROMPT_WITH_ATS = """You are a resume screener and an ATS (Applicant Tracking System)
keyword-matching engine. Read the resume text and the target job description below, then
respond ONLY with a JSON object, no markdown fences, no preamble, in this exact shape:
{{"score": <integer 0-100, overall candidate fit for the role>, "summary": "<2 sentence summary>",
"top_skills": ["skill1", "skill2"], "ats_score": <integer 0-100, keyword/skill match against the job description>,
"ats_summary": "<1-2 sentences on which required keywords/skills are present or missing>"}}

Job description:
{job_description}

Resume text:
{resume_text}
"""


def extract_text_from_resume(file_bytes: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        text = ""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text.strip()

    # fallback: treat as plain text (docx handling can be added with python-docx)
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def is_resume(text: str) -> bool:
    """
    Classifies whether extracted document text is actually a resume, so sync
    only tracks attachments worth tracking instead of every PDF in the inbox.
    Fails closed (returns False) on any error or unparseable response.
    """
    if not settings.GEMINI_API_KEY or not text.strip():
        return False

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        prompt = RESUME_CLASSIFICATION_PROMPT.format(text=text[:6000])
        response = model.generate_content(prompt)

        usage = response.usage_metadata
        usage_service.record_call(usage.prompt_token_count, usage.candidates_token_count, usage.total_token_count)

        raw = re.sub(r"^```json\s*|\s*```$", "", response.text.strip())
        return bool(json.loads(raw).get("is_resume", False))
    except Exception:
        return False


def score_resume(resume_text: str, job_description: str = "") -> Dict:
    if not settings.GEMINI_API_KEY:
        raise ValueError("No Gemini API key available — set GEMINI_API_KEY in .env")

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    job_description = (job_description or "").strip()
    if job_description:
        prompt = SCORING_PROMPT_WITH_ATS.format(
            resume_text=resume_text[:12000], job_description=job_description[:4000]
        )
    else:
        prompt = SCORING_PROMPT.format(resume_text=resume_text[:12000])  # guard against huge inputs

    response = model.generate_content(prompt)

    usage = response.usage_metadata
    usage_service.record_call(usage.prompt_token_count, usage.candidates_token_count, usage.total_token_count)

    raw = response.text.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"score": 0, "summary": "Could not parse model response", "top_skills": []}

    if not job_description:
        parsed.setdefault("ats_score", None)
        parsed.setdefault("ats_summary", "Set a target job description in Settings to enable ATS matching.")

    return parsed
