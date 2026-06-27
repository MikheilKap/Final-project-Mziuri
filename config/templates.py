"""Jinja2Templates instance used by every router.
"""
from datetime import date

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def _days_until(date_str: str):
    """Return days until a YYYY-MM-DD string, or None on error."""
    if not date_str:
        return None
    try:
        return (date.fromisoformat(str(date_str)) - date.today()).days
    except (ValueError, TypeError):
        return None


templates.env.filters["days_until"] = _days_until
