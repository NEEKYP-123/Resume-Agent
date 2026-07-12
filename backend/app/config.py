import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Admin auth
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = 60 * 12

    # Base URL of the frontend, used to build the password-reset link
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5501")

    # Gmail API (OAuth 2.0)
    GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
    GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN", "")
    GMAIL_LABEL_FILTER = os.getenv("GMAIL_LABEL_FILTER", "Resumes")
    GMAIL_PROCESSED_LABEL = os.getenv("GMAIL_PROCESSED_LABEL", "ResumeAgent-Processed")

    # MongoDB Atlas
    MONGODB_URI = os.getenv("MONGODB_URI", "")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "resume_agent")
    MONGODB_COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME", "resumes")

    # Backblaze B2 (S3-compatible)
    B2_ENDPOINT = os.getenv("B2_ENDPOINT", "")
    B2_KEY_ID = os.getenv("B2_KEY_ID", "")
    B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY", "")
    B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "resume-agent-files")

    # Gemini (server-side default key; users can override with their own key per-request)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Local dev mode - use local disk + a local JSON file instead of real MongoDB/B2, for testing without credentials
    LOCAL_MODE = os.getenv("LOCAL_MODE", "true").lower() == "true"


settings = Settings()
