# Resume Agent

An admin console that automates resume screening. It scans a Gmail inbox for resume
attachments (no manual labeling required), uses Gemini to classify and score each one
— both a general fit score and an ATS-style keyword match against a job posting —
then surfaces everything in a role-aware dashboard for admins and recruiters to review,
shortlist, annotate, and export.

**Status: actively being built.** This is not a finished product — auth hardening, roles,
job postings, and the whole-inbox scan are all recent additions, and there are known gaps
documented below.

## How it works

```
Gmail inbox
   │  has:attachment, excluding already-scanned emails
   ▼
Gemini classifies: "is this attachment actually a resume?"
   │  (fails closed — errors are treated as "no")
   ▼
Backblaze B2 (raw file)  +  MongoDB (tracking record)
   │
   ▼
Gemini scores: fit score + ATS match vs. the assigned job's description
   │  (or the global fallback description, if unassigned)
   ▼
Dashboard: shortlist/reject, assign to a job, leave notes, export CSV
```

Every scanned email — resume or not — gets labeled `ResumeAgent-Processed` in Gmail so
it's never re-scanned. Reassigning a resume to a different job immediately re-triggers
scoring against the new description, so scores don't go stale.

## Features

- **Gmail intake**: whole-inbox scan, Gemini-classified — no manual "Resumes" label needed
- **Dual scoring**: general fit score + ATS keyword-match score, both with human-readable
  reasoning viewable in a details modal (not just a hover tooltip)
- **Job postings**: create/edit/close (admin), open read visibility for everyone, per-job
  candidate counts that filter the dashboard on click
- **Notes**: per-candidate, per-recruiter-private (admin sees every author's notes)
- **Roles**: Admin (manage users, jobs, quota, full visibility) vs Recruiter (screen,
  shortlist, notes, scoped visibility)
- **Auth**: JWT sessions with configurable timeout, login rate-limiting/lockout, email-based
  password reset (hashed, single-use, 30-minute tokens) for both the admin account and any
  signed-up user
- **Session persistence**: reloading the page doesn't force a re-login
- **Gemini usage tracking**: call count + token totals, admin-only, under Settings
- **CSV export**, **dark/light theme**, **CSV/local-mode fallback** for testing without any
  cloud credentials

## Project structure

```
resume-agent/
  backend/
    app/
      main.py                    FastAPI app entrypoint, router registration
      config.py                  env-based settings (Settings class, os.getenv)
      auth.py                    JWT issuance/verification, get_current_user, require_admin
      routes/
        auth_routes.py           /login /signup /verify /forgot-password /reset-password
        resumes.py                /sync /score /assign-job /notes /export/csv
        job_routes.py              /jobs (list/create/update/close)
        user_routes.py              /users (list/set-role/delete) — admin only
        usage_routes.py              /usage — admin only
        settings_routes.py            /settings/job-description (global fallback)
      services/
        gmail_service.py          Gmail OAuth2: fetch/classify-candidates, relabel, send mail
        b2_service.py              Backblaze B2 file storage (local disk fallback)
        mongodb_service.py          resume tracking: create/update/list, job assignment, notes
        gemini_service.py            text extraction, is_resume() classifier, score_resume()
        admin_service.py             legacy .env admin: password hash override
        users_service.py             signed-up accounts: email, role, password
        password_reset_service.py    hashed single-use reset tokens (admin + users, unified)
        login_security_service.py    failed-attempt tracking + lockout
        job_postings_service.py      job posting CRUD
        usage_service.py             Gemini call/token counters
        settings_service.py          global fallback job description
        security.py                   shared password/token hashing helpers
    tests/
      conftest.py                 fixtures: isolated local-mode storage, stubbed Gmail send
      test_auth.py                login, lockout, signup, verify, password reset
      test_roles.py                job/user/notes/usage RBAC
    get_gmail_token.py           one-time OAuth script to mint a refresh token
    requirements.txt
    .env.example
  frontend/
    index.html                   entire dashboard: login/signup/reset, sync, scoring,
                                  job postings, user management, usage, notes, theming
```

## Running it locally (no cloud credentials needed yet)

By default `LOCAL_MODE=true` — every service (Mongo, B2, admin credentials, reset tokens,
rate-limit counters, job postings, usage stats) falls back to a JSON file under
`backend/local_storage/`. This lets you exercise the whole pipeline except Gmail sync and
Gemini scoring, which need real API keys regardless of mode.

```bash
cd backend
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# at minimum, fill in GEMINI_API_KEY to test scoring
uvicorn app.main:app --reload --port 8000
```

Then serve `frontend/index.html` (e.g. `python -m http.server 5501` from the frontend
folder) and open it in your browser. Log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from
`.env` (defaults: `admin` / `changeme`).

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Yes | Legacy single-admin login; overridden by a stored hash once "Forgot password" is used |
| `ADMIN_EMAIL` | For password reset | Where the admin's reset link gets sent |
| `JWT_SECRET` | Yes | Sign with a long random string in any real deployment |
| `SESSION_TIMEOUT_MINUTES` | No (default `30`) | JWT expiry |
| `FRONTEND_URL` | For password reset | Used to build the reset link |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` | For Gmail sync + reset emails | See below |
| `GMAIL_PROCESSED_LABEL` | No (default `ResumeAgent-Processed`) | Gmail label applied to every scanned email |
| `MONGODB_URI` / `MONGODB_DB_NAME` / `MONGODB_COLLECTION_NAME` | For cloud mode | Leave blank while `LOCAL_MODE=true` |
| `B2_ENDPOINT` / `B2_KEY_ID` / `B2_APPLICATION_KEY` / `B2_BUCKET_NAME` | For cloud mode | Leave blank while `LOCAL_MODE=true` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Yes | Default model `gemini-2.5-flash` |
| `LOCAL_MODE` | No (default `true`) | Set `false` once Mongo/B2 are wired up |

## Wiring up the real integrations

1. **Gmail**: create OAuth client credentials (Desktop app type) in Google Cloud Console,
   run `python get_gmail_token.py` (needs scopes `gmail.modify` and `gmail.send` — modify
   to label scanned emails, send to deliver password-reset emails), then set
   `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` in `.env`. No Gmail label
   needs to be applied manually — the whole inbox gets scanned automatically.
2. **MongoDB Atlas**: create a free cluster, a database user, allow your IP under Network
   Access, and set `MONGODB_URI` in `.env`.
3. **Backblaze B2**: create a bucket, an application key scoped to it, and set `B2_ENDPOINT`,
   `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME` in `.env`.
4. **Gemini**: get a key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   and set `GEMINI_API_KEY`.
5. Once Mongo and B2 are wired up, set `LOCAL_MODE=false`.

## Auth & security notes

- Passwords are hashed with salted PBKDF2 (`security.py`), never stored or compared in
  plaintext once a reset has occurred.
- Reset tokens are stored only as a SHA-256 hash, expire after 30 minutes, and are deleted
  on first use — the plaintext token only ever exists in the emailed link.
- Login lockout (5 failed attempts → 15-minute lockout) is keyed on whatever username string
  was submitted, including nonexistent ones, so lockout timing can't be used to enumerate
  real accounts. Same principle applies to `forgot-password`: the response is identical
  whether or not the email exists.
- Role (`admin`/`recruiter`) is re-resolved from the database on every request via the
  `get_current_user` dependency — never trusted from the JWT payload — so a demoted or
  removed user loses access on their very next call, not just their next login.
- Recruiter notes are filtered server-side per viewer (`_filter_notes_for_viewer` in
  `resumes.py`) — a recruiter genuinely cannot fetch another recruiter's notes over the API,
  it's not just hidden in the UI.
- CORS is wide open (`*`) for local dev — tighten `allow_origins` in `main.py` before
  deploying anywhere public.

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

30 tests covering login/lockout/signup/session-verification/password-reset and
job/user/notes/usage role-based access control. Every test runs against a temp-directory
copy of local-mode storage (see `tests/conftest.py`) and Gmail sending is stubbed out
entirely — the suite never touches your real data or makes a real API call.

## Known gaps / simplified for now

- `.doc`/`.docx` text extraction isn't implemented — only PDFs (`pdfplumber`) actually work;
  Word attachments will fail extraction and get silently skipped during classification.
- `/api/resumes/sync` is a manual dashboard button; wire it to a scheduler (cron, cloud
  scheduler) if you want it running unattended.
- The whole-inbox scan means the first sync after enabling it may process a backlog of
  unrelated attachments (invoices, etc.) — each one costs a Gemini classification call.
  The 20-per-sync cap throttles this across multiple syncs rather than doing it all at once.
- Gemini usage tracking is a running counter (call count + token totals), not full
  cost/billing accounting.
- Single-organization only — there's no multi-tenant/org concept, one shared workspace
  for every admin/recruiter account.
