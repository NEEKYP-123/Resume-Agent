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

SCORING_PROMPT = """You are a resume screener. Read the resume text below and respond
ONLY with a JSON object, no markdown fences, no preamble, in this exact shape:
{{"score": <integer 0-100>, "summary": "<2 sentence summary>", "top_skills": ["skill1", "skill2"]}}

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


def score_resume(resume_text: str) -> Dict:
    if not settings.GEMINI_API_KEY:
        raise ValueError("No Gemini API key available — set GEMINI_API_KEY in .env")

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = SCORING_PROMPT.format(resume_text=resume_text[:12000])  # guard against huge inputs
    response = model.generate_content(prompt)

    raw = response.text.strip()
    raw = re.sub(r"^```json\s*|\s*```$", "", raw.strip())

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"score": 0, "summary": "Could not parse model response", "top_skills": []}

    return parsed
