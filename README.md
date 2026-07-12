# Resume Agent

Pulls resume attachments from a labeled Gmail inbox, stores the files in Backblaze B2,
tracks each one in MongoDB Atlas, and scores them with Gemini — behind a small
JWT-authenticated admin dashboard with sync, scoring, CSV export, and password reset.

## Structure

```
resume-agent/
  backend/
    app/
      main.py                # FastAPI app entrypoint
      config.py               # env-based settings
      auth.py                 # JWT admin auth
      routes/
        auth_routes.py        # /api/auth/login, /forgot-password, /reset-password
        resumes.py             # /api/resumes/sync, /score, /export/csv
      services/
        gmail_service.py       # Gmail OAuth2 — fetch attachments, relabel, send reset email
        b2_service.py           # Backblaze B2 file storage (local disk fallback)
        mongodb_service.py      # MongoDB Atlas tracking (local JSON fallback)
        admin_service.py        # password hashing + reset tokens
        gemini_service.py       # text extraction + AI scoring
    get_gmail_token.py         # one-time OAuth script to mint a refresh token
    requirements.txt
    .env.example
  frontend/
    index.html                 # dashboard: login, sync, score, CSV export, dark/light theme
```

## Running it locally (no cloud credentials needed yet)

By default `LOCAL_MODE=true`, so B2 becomes a local folder and MongoDB becomes a JSON file.
This lets you test the whole flow except Gmail sync and Gemini scoring, which need real API keys.

```bash
cd backend
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# at minimum, fill in GEMINI_API_KEY to test scoring
uvicorn app.main:app --reload --port 8000
```

Then serve `frontend/index.html` (e.g. `python -m http.server 5501` from the frontend folder)
and open it in your browser. Log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`
(defaults: `admin` / `changeme`).

## Wiring up the real integrations

1. **Gmail**: create OAuth client credentials (Desktop app type) in Google Cloud Console,
   run `python get_gmail_token.py` (needs scopes `gmail.modify` and `gmail.send` — modify
   to relabel processed emails, send to deliver password-reset emails), then set
   `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` in `.env`. Apply a Gmail
   label (default `Resumes`) to the emails you want synced.
2. **MongoDB Atlas**: create a free cluster, a database user, allow your IP under Network
   Access, and set `MONGODB_URI` in `.env`.
3. **Backblaze B2**: create a bucket, an application key scoped to it, and set `B2_ENDPOINT`,
   `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME` in `.env`.
4. **Gemini**: get a key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   and set `GEMINI_API_KEY`. Default model is `gemini-2.5-flash`.
5. Once all three cloud services are wired up, set `LOCAL_MODE=false`.

## Password reset

"Forgot password?" on the login page emails a time-limited reset link (via Gmail) to the
same account gmail_service is authorized against. The admin password starts as
`ADMIN_PASSWORD` from `.env`, but once reset, it's stored as a salted hash (MongoDB, or
locally in `local_storage/admin.json`) and takes precedence over the `.env` value.

## Notes on what's simplified

- `/api/resumes/sync` is exposed as a manual dashboard button; wire it to a scheduled job
  (cron, cloud scheduler) if you want it running unattended.
- Resume text extraction currently handles PDFs (via `pdfplumber`); add `python-docx` in
  `gemini_service.py` for `.docx` support.
- CORS is wide open (`*`) for local dev — tighten `allow_origins` in `main.py` before
  deploying anywhere public.
