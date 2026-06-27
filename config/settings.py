from dotenv import load_dotenv
import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("API_KEY")

GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_CLIENT_SECRET = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()

SECRET_KEY = os.getenv("SECRET_KEY", "subtracker-dev-secret-change-in-production")

INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
OAUTH_TOKENS_DIR = os.path.join(INSTANCE_DIR, "tokens")
OAUTH_REDIRECT_URI = os.getenv(
    "OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/scanner/callback"
)


def oauth_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
