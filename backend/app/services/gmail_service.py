"""
Gmail service — handles OAuth 2.0 auth, pulls resume attachments from the
inbox (filtered by label, e.g. "Resumes"), relabels each processed email so a
repeat sync doesn't re-fetch (and re-create tracking entries for) it, and
sends the admin password-reset email.

To get a refresh token the first time:
1. Create OAuth client credentials in Google Cloud Console (Desktop app type).
2. Run get_gmail_token.py, which uses google-auth-oauthlib's InstalledAppFlow
   with scopes "gmail.modify" (move labels after processing) and "gmail.send"
   (deliver the password-reset email).
3. Save the resulting refresh_token into your .env as GMAIL_REFRESH_TOKEN.
"""
import base64
from email.mime.text import MIMEText
from typing import List, Dict

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


def _get_gmail_client():
    creds = Credentials(
        token=None,
        refresh_token=settings.GMAIL_REFRESH_TOKEN,
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


def fetch_resume_emails(max_results: int = 20) -> List[Dict]:
    """
    Returns a list of dicts: {message_id, sender, subject, date, attachments: [{filename, data (bytes)}]}
    """
    service = _get_gmail_client()
    query = f"label:{settings.GMAIL_LABEL_FILTER} has:attachment"

    results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    messages = results.get("messages", [])

    parsed = []
    for msg_ref in messages:
        msg = service.users().messages().get(userId="me", id=msg_ref["id"]).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

        attachments = []
        parts = msg["payload"].get("parts", [])
        for part in parts:
            filename = part.get("filename")
            if filename and part["body"].get("attachmentId"):
                att_id = part["body"]["attachmentId"]
                att = service.users().messages().attachments().get(
                    userId="me", messageId=msg["id"], id=att_id
                ).execute()
                file_data = base64.urlsafe_b64decode(att["data"])
                attachments.append({"filename": filename, "data": file_data})

        if attachments:
            parsed.append({
                "message_id": msg["id"],
                "sender": headers.get("From", "unknown"),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "attachments": attachments,
            })

    return parsed


def _get_label_id(service, label_name: str, create_if_missing: bool = False) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == label_name:
            return label["id"]

    if not create_if_missing:
        raise ValueError(f"Gmail label '{label_name}' not found")

    created = service.users().labels().create(
        userId="me",
        body={"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    return created["id"]


def mark_processed(message_id: str):
    """
    Moves a synced email out of the source label (GMAIL_LABEL_FILTER) and into
    the processed label (GMAIL_PROCESSED_LABEL), so it's excluded from the next sync's query.
    """
    service = _get_gmail_client()
    source_label_id = _get_label_id(service, settings.GMAIL_LABEL_FILTER)
    processed_label_id = _get_label_id(service, settings.GMAIL_PROCESSED_LABEL, create_if_missing=True)

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": [source_label_id], "addLabelIds": [processed_label_id]},
    ).execute()


def get_own_email_address() -> str:
    service = _get_gmail_client()
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]


def send_email(subject: str, body_text: str):
    """
    Sends an email from the authorized account to itself (used for the
    password-reset link, since this app has a single admin whose inbox is
    the same account it's already authorized against).
    """
    service = _get_gmail_client()
    to_address = get_own_email_address()

    message = MIMEText(body_text)
    message["to"] = to_address
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    service.users().messages().send(userId="me", body={"raw": raw}).execute()
