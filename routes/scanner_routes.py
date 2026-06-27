import os
import json
import logging
from datetime import date

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from config.templates import templates
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    OAUTH_TOKENS_DIR,
    OAUTH_REDIRECT_URI,
    oauth_configured,
)
from database.auth import get_user_id, require_login
from database.template_context import build_template_context
from database.subscriptions import import_subscriptions, upsert_subscription
from services.email_analyzer import prefilter_emails, analyze_with_ai, dedupe_subscriptions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scanner")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_flow_store = {}


async def scanner_context(request, **extra):
    ctx = await build_template_context(request, **extra)
    ctx["oauth_configured"] = oauth_configured()
    ctx.setdefault("subscriptions", [])
    ctx.setdefault("subscriptions_json", "[]")
    ctx.setdefault("today", date.today().isoformat())
    return ctx


def parse_gmail_error(exc: HttpError) -> tuple[str, bool]:
    status = exc.resp.status
    raw = exc.content.decode("utf-8", errors="replace") if exc.content else ""
    api_message = ""
    reasons: list[str] = []

    try:
        payload = json.loads(raw)
        err = payload.get("error", {})
        api_message = err.get("message", "")
        reasons = [e.get("reason", "") for e in err.get("errors", [])]
    except (json.JSONDecodeError, AttributeError):
        api_message = raw or str(exc)

    if status == 401:
        return "Gmail access expired. Please reconnect your account.", True

    if status == 403 and (
        "accessNotConfigured" in reasons
        or "Gmail API has not been used" in api_message
        or "Gmail API has not been enabled" in api_message
    ):
        return (
            "Gmail API is not enabled for your Google Cloud project. "
            "Open Google Cloud Console → APIs & Services → Library → search "
            '"Gmail API" → Enable. Wait 2–5 minutes, then run the scan again '
            "(you do not need to reconnect Gmail).",
            False,
        )

    if status == 403:
        return (
            api_message
            or "Gmail denied access. Check that Gmail API is enabled and your "
            "Google account is listed as a test user on the OAuth consent screen.",
            False,
        )

    return api_message or f"Gmail scan failed (HTTP {status}).", False


def token_path_for_user(user_id: int) -> str:
    return os.path.join(OAUTH_TOKENS_DIR, f"{user_id}.json")


def get_gmail_service(user_id: int):
    token_file = token_path_for_user(user_id)
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleRequest())
                with open(token_file, "w") as token:
                    token.write(creds.to_json())
            except Exception:
                if os.path.exists(token_file):
                    os.remove(token_file)
                return None
        else:
            return None
    return build("gmail", "v1", credentials=creds)


GMAIL_SCAN_QUERY = (
    'subject:subscription OR subject:renewal OR subject:membership OR subject:premium '
    'OR subject:"auto-renew" OR subject:"billing" OR subject:invoice OR subject:receipt'
)


def _header(headers: list, name: str) -> str:
    return next((h["value"] for h in headers if h["name"] == name), "")


def _extract_body_text(payload: dict) -> str:
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    import base64
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            nested = _extract_body_text(part)
            if nested:
                return nested
    elif payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            import base64
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


def fetch_candidate_emails(service, max_results: int = 50) -> list[dict]:
    logger.info(f"Fetching emails with query: {GMAIL_SCAN_QUERY}")
    results = (
        service.users()
        .messages()
        .list(userId="me", q=GMAIL_SCAN_QUERY, maxResults=max_results)
        .execute()
    )
    messages = results.get("messages") or []
    logger.info(f"Gmail returned {len(messages)} messages")
    emails = []

    for msg in messages:
        msg_data = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="full")
            .execute()
        )
        headers = msg_data.get("payload", {}).get("headers", [])
        payload = msg_data.get("payload", {})
        body = _extract_body_text(payload)
        subject = _header(headers, "Subject") or "No Subject"
        sender = _header(headers, "From")
        logger.info(f"Fetched email: subject='{subject}', from='{sender}', body_length={len(body)}")
        emails.append({
            "subject": subject,
            "from": sender,
            "date": _header(headers, "Date"),
            "body": body[:2000],
        })

    return emails


def build_oauth_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [OAUTH_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI,
    )


@router.get("/", response_class=HTMLResponse)
async def view_scanner_home(request: Request, msg: str = None):
    redirect = require_login(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)
    service = get_gmail_service(user_id)
    success = None
    if msg == "connected":
        success = "Gmail connected successfully!"
    elif msg == "success":
        success = "Successfully logged in!"

    context = await scanner_context(
        request,
        authenticated=service is not None,
        searched=False,
        grouped_results={},
        success_message=success,
        error_message=None,
        pending_subs_json="[]",
        skipped_emails=[],
    )
    return templates.TemplateResponse(request=request, name="scanner.html", context=context)


@router.get("/connect")
async def connect_google_oauth(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    if not oauth_configured():
        context = await scanner_context(
            request,
            authenticated=False,
            error_message=(
                "Google OAuth is not configured. Add GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET to your .env file."
            ),
        )
        return templates.TemplateResponse(request=request, name="scanner.html", context=context)

    flow = build_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _flow_store[state] = flow.code_verifier
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def oauth_callback(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    if not oauth_configured():
        return RedirectResponse(url="/scanner/?msg=oauth_error", status_code=303)

    try:
        state = request.query_params.get("state")
        code_verifier = _flow_store.pop(state, None)

        flow = build_oauth_flow()
        flow.fetch_token(
            authorization_response=str(request.url), code_verifier=code_verifier
        )
        creds = flow.credentials

        user_id = get_user_id(request)
        os.makedirs(OAUTH_TOKENS_DIR, exist_ok=True)
        token_file = token_path_for_user(user_id)
        with open(token_file, "w") as token:
            token.write(creds.to_json())
        return RedirectResponse(url="/scanner/?msg=connected", status_code=303)
    except Exception as exc:
        logger.exception("OAuth callback failed")
        context = await scanner_context(
            request,
            authenticated=False,
            error_message=f"Gmail connection failed: {exc}",
        )
        return templates.TemplateResponse(request=request, name="scanner.html", context=context)


@router.get("/scan", response_class=HTMLResponse)
async def run_scan(request: Request):
    """Scan Gmail and return detected subscriptions with confidence scores.
    Nothing is saved to the dashboard yet, the user reviews and confirms."""
    redirect = require_login(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)
    service = get_gmail_service(user_id)
    if not service:
        return RedirectResponse(url="/scanner/connect")

    try:
        raw_emails = fetch_candidate_emails(service)
        logger.info(f"Fetched {len(raw_emails)} raw emails from Gmail")

        filtered_emails, skipped = prefilter_emails(raw_emails)
        logger.info(f"Prefilter kept {len(filtered_emails)} emails, skipped {len(skipped)}")

        detected = dedupe_subscriptions(analyze_with_ai(filtered_emails))
        logger.info(f"Detected {len(detected)} subscriptions")

        # Sort by confidence descending so high-confidence appear first
        detected.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        pending_subs_json = json.dumps(detected)

        context = await scanner_context(
            request,
            authenticated=True,
            searched=True,
            pending_subs=detected,
            pending_subs_json=pending_subs_json,
            skipped_emails=skipped,
            scan_count=len(filtered_emails),
            grouped_results={},
        )
        return templates.TemplateResponse(request=request, name="scanner.html", context=context)

    except HttpError as exc:
        logger.exception("Gmail API error during scan")
        error, disconnect = parse_gmail_error(exc)
        if disconnect:
            token_file = token_path_for_user(user_id)
            if os.path.exists(token_file):
                os.remove(token_file)
        context = await scanner_context(
            request,
            authenticated=not disconnect,
            searched=False,
            error_message=error,
            pending_subs_json="[]",
            skipped_emails=[],
        )
        return templates.TemplateResponse(request=request, name="scanner.html", context=context)
    except Exception as exc:
        logger.exception("Unexpected scan error")
        context = await scanner_context(
            request,
            authenticated=True,
            error_message=f"Scan failed: {exc}",
            pending_subs_json="[]",
            skipped_emails=[],
        )
        return templates.TemplateResponse(request=request, name="scanner.html", context=context)


@router.post("/import-selected")
async def import_selected(request: Request):
    """Import the user-selected subscriptions from the review screen."""
    redirect = require_login(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)

    try:
        body = await request.json()
        subs = body.get("subscriptions", [])
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    if not subs:
        return JSONResponse({"ok": False, "error": "No subscriptions provided"}, status_code=400)

    result = await import_subscriptions(user_id, subs)
    added = len(result["added"])
    updated = len(result["updated"])
    return JSONResponse({"ok": True, "added": added, "updated": updated})


@router.get("/disconnect")
async def disconnect_gmail(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)
    token_file = token_path_for_user(user_id)
    if os.path.exists(token_file):
        os.remove(token_file)
    return RedirectResponse(url="/scanner/", status_code=303)
