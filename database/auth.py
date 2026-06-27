import re

from email_validator import EmailNotValidError, validate_email as ev_validate
from fastapi import Request
from fastapi.responses import RedirectResponse

VALID_TLDS = frozenset({
    "com", "net", "org", "edu", "gov", "mil", "int", "io", "co", "uk", "de", "fr",
    "it", "es", "nl", "be", "at", "ch", "pl", "se", "no", "dk", "fi", "pt", "ie",
    "ca", "us", "au", "nz", "in", "jp", "kr", "cn", "ru", "br", "mx", "ar", "za",
    "sg", "hk", "tw", "my", "ph", "th", "vn", "id", "ae", "sa", "il", "tr", "gr",
    "cz", "hu", "ro", "ua", "info", "biz", "me", "tv", "cc", "app", "dev", "tech",
    "cloud", "online", "store", "live", "pro", "xyz", "club", "site", "space",
    "email", "gmail", "googlemail", "outlook", "hotmail", "yahoo", "icloud", "proton",
    "protonmail", "aol", "mail", "yandex", "gmx", "live", "msn",
})

BLOCKED_DOMAINS = frozenset({
    "example.com", "test.com", "fake.com", "invalid.com", "localhost",
})


def validate_email(email: str) -> str | None:
    email = email.strip()
    if not email:
        return "Please enter a valid email address."

    try:
        result = ev_validate(email, check_deliverability=True)
        normalized = result.normalized
    except EmailNotValidError:
        return "Please enter a real, working email address."

    domain = normalized.rsplit("@", 1)[-1]
    if domain in BLOCKED_DOMAINS:
        return "Please use a real email address."

    tld = domain.rsplit(".", 1)[-1]
    if tld not in VALID_TLDS:
        return "Please use an email with a recognized domain (e.g. gmail.com, outlook.com)."

    local = normalized.split("@")[0]
    if re.fullmatch(r"[0-9._+-]+", local) or len(local) < 2:
        return "Please enter a valid email address."

    return None


def get_user_id(request: Request) -> int | None:
    user_id = request.session.get("user_id")
    return int(user_id) if user_id is not None else None


def get_username(request: Request) -> str | None:
    return request.session.get("username")


def require_login(request: Request) -> RedirectResponse | None:
    if get_user_id(request) is None:
        return RedirectResponse(url="/login", status_code=303)
    return None
