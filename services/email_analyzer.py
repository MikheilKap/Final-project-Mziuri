import json
import re
import logging
from datetime import date, timedelta, datetime

import requests

from config.settings import API_KEY

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

SKIP_SUBJECT_PHRASES = (
    "payment failed",
    "payment declined",
    "charge failed",
    "card declined",
    "payment declined",
    "refunded",
    "refund issued",
    "unsuccessful",
    "did not go through",
    "verification failed",
    "past due",
    "overdue notice",
    "free trial",
    "trial receipt",
    "trial ending",
    "trial expired",
    "trial has ended",
    "your trial has ended",
    "subscription expired",
    "subscription has expired",
    "subscription ended",
    "subscription cancelled",
    "subscription canceled",
    "cancelled subscription",
    "canceled subscription",
    "your subscription has been cancelled",
    "your subscription has been canceled",
    "we're sorry to see you go",
    "sorry to see you go",
    "goodbye",
)

ACTIVE_OVERRIDE_PHRASES = (
    "subscription is active",
    "subscription's active",
    "is now active",
    "successfully renewed",
    "payment successful",
    "payment received",
    "renews on",
    "next billing date",
    "next payment",
)

GENERIC_SENDER_DOMAINS = (
    "blogger",
    "redditmail",
    "updates",
    "announce",
    "notification",
    "noreply",
    "no-reply",
    "donotreply",
)

KNOWN_SUBSCRIPTION_BRANDS = (
    "netflix",
    "spotify",
    "youtube",
    "google",
    "apple",
    "amazon",
    "microsoft",
    "adobe",
    "discord",
    "patreon",
    "github",
    "dropbox",
    "slack",
    "zoom",
    "notion",
    "canva",
    "figma",
    "chatgpt",
    "openai",
    "midjourney",
    "streamflix",
    "hulu",
    "disney",
    "paramount",
    "peacock",
    "crunchyroll",
    "audible",
    "duolingo",
    "grammarly",
    "lastpass",
    "nordvpn",
    "expressvpn",
    "1password",
)

SUBSCRIPTION_HINTS = (
    "subscription",
    "subscribed",
    "renewal",
    "renew",
    "auto-renew",
    "membership",
    "premium",
    "billing cycle",
    "your plan",
    "is active",
    "will renew",
    "recurring",
    "invoice",
    "receipt",
)

# ── Category mapping ──────────────────────────────────────────────────────────
CATEGORY_MAP = {
    "Streaming": [
        "netflix", "hulu", "disney", "paramount", "peacock", "crunchyroll",
        "hbo", "max", "apple tv", "youtube premium", "youtube tv",
        "discovery", "fubo", "sling", "espn",
    ],
    "Music": [
        "spotify", "apple music", "tidal", "deezer", "pandora", "soundcloud",
        "amazon music", "youtube music",
    ],
    "Gaming": [
        "xbox", "playstation", "nintendo", "steam", "ea play", "game pass",
        "geforce now", "stadia", "twitch",
    ],
    "Productivity": [
        "microsoft 365", "office 365", "google workspace", "notion",
        "slack", "zoom", "dropbox", "box", "evernote", "todoist", "asana",
        "monday", "jira", "confluence", "basecamp",
    ],
    "AI Tools": [
        "openai", "chatgpt", "midjourney", "claude", "anthropic",
        "github copilot", "jasper", "copy.ai", "writesonic",
    ],
    "Design": [
        "adobe", "canva", "figma", "sketch", "invision", "framer",
    ],
    "Security": [
        "nordvpn", "expressvpn", "1password", "lastpass", "dashlane",
        "bitwarden", "surfshark",
    ],
    "Cloud": [
        "aws", "amazon web", "google cloud", "azure", "digitalocean",
        "heroku", "vercel", "netlify", "github", "gitlab",
    ],
    "Learning": [
        "duolingo", "coursera", "udemy", "skillshare", "masterclass",
        "audible", "kindle", "scribd", "blinkist",
    ],
    "Social": [
        "discord", "patreon", "twitter", "x premium", "reddit premium",
        "linkedin premium",
    ],
}

# ── Currency symbol → ISO code map ───────────────────────────────────────────
CURRENCY_SYMBOLS = {
    "$":  "USD",
    "€":  "EUR",
    "£":  "GBP",
    "₾":  "GEL",
    "₺":  "TRY",
    "¥":  "JPY",
    "₩":  "KRW",
    "₹":  "INR",
    "A$": "AUD",
    "C$": "CAD",
    "CHF": "CHF",
    "R":  "ZAR",
    "kr": "SEK",
}


def categorize_subscription(name: str) -> str:
    """Return the category for a subscription name."""
    name_lower = name.lower()
    for category, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "Other"


def _compute_confidence(name: str, cost: float, renewal_date: str | None,
                        subject: str, body: str, ai_hint: int | None = None) -> int:
    """Compute a confidence score (0–100) from concrete email signals.

    The LLM's suggestion (ai_hint) is only used as a 25 % blend so it can
    never flat-line every result at the same value — the signal scoring always
    dominates.
    """
    score = 40  # baseline: email already cleared the prefilter

    subject_lower = subject.lower()
    body_lower    = body.lower()

    # ── Strong positive signals (+) ──────────────────────────────────
    RECEIPT_PHRASES = (
        "payment received", "payment successful", "successfully charged",
        "your payment of", "we've charged", "we charged", "amount charged",
        "your receipt", "receipt for", "order confirmation",
        "thank you for your payment", "thank you for subscribing",
        "your subscription is active", "subscription confirmed",
        "successfully renewed", "renewal confirmation",
        "your plan is active", "billing confirmation",
        "invoice #", "invoice no", "transaction id",
    )
    receipt_hits = sum(
        1 for p in RECEIPT_PHRASES
        if p in body_lower or p in subject_lower
    )
    score += min(receipt_hits * 12, 36)   # up to +36

    # Renewal date was actually extracted (not a computed ±30/365 day default)
    if renewal_date:
        default_monthly = (date.today() + timedelta(days=30)).isoformat()
        default_yearly  = (date.today() + timedelta(days=365)).isoformat()
        if renewal_date not in (default_monthly, default_yearly):
            score += 10   # real date found in email body

    # Known subscription brand
    if any(brand in name.lower() for brand in KNOWN_SUBSCRIPTION_BRANDS):
        score += 8

    # Multiple currency / price signals in body (strong indicator of a receipt)
    PRICE_SIGNALS = ("$", "€", "£", "₾", "usd", "eur", "gbp", "gel",
                     "/month", "/year", "per month", "per year", "/mo", "/yr",
                     "billing amount", "charge amount")
    price_hits = sum(1 for p in PRICE_SIGNALS if p in body_lower)
    score += min(price_hits * 3, 12)      # up to +12

    # ── Negative / uncertainty signals (-) ───────────────────────────
    UNCERTAINTY_PHRASES = (
        "free", "trial", "promotional", "complimentary", "offer",
        "newsletter", "unsubscribe from", "marketing", "you're invited",
        "limited time", "discount", "promo code", "coupon",
    )
    uncertainty_hits = sum(
        1 for p in UNCERTAINTY_PHRASES
        if p in body_lower or p in subject_lower
    )
    score -= min(uncertainty_hits * 8, 28)  # up to -28

    # ── Blend the LLM hint at 25 % weight ────────────────────────────
    # This lets the AI break ties between similar emails without being
    # able to assign a uniform score to everything.
    if ai_hint is not None:
        try:
            score = int(score * 0.75 + int(ai_hint) * 0.25)
        except (TypeError, ValueError):
            pass

    return max(10, min(99, score))


def ask_groq(prompt: str, system: str | None = None) -> str:
    if not API_KEY:
        raise RuntimeError("Groq API key is not configured.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": MODEL, "messages": messages},
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _extract_json_array(text: str) -> list:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    return json.loads(text[start : end + 1])


def prefilter_emails(emails: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    skipped: list[str] = []
    seen_subjects: set[str] = set()

    EXPIRED_BODY_PHRASES = (
        "trial has ended",
        "trial has expired",
        "your trial has ended",
        "free trial has ended",
        "free trial has expired",
        "subscription has ended",
        "subscription ended",
        "subscription cancelled",
        "subscription canceled",
        "cancelled subscription",
        "canceled subscription",
        "we're sorry to see you go",
        "sorry to see you go",
        "goodbye",
        "your subscription is no longer active",
        "subscription is no longer active",
        "expired subscription",
        "subscription expired",
        "your free trial",
        "your trial period",
    )

    for item in emails:
        subject = (item.get("subject") or "").strip()
        sender = (item.get("from") or "").lower()
        body = (item.get("body") or "").lower()
        subject_lower = subject.lower()
        norm = re.sub(r"\s+", " ", subject_lower)

        if not subject or subject_lower == "no subject":
            logger.info(f"Skipping: '{subject}' - empty subject")
            skipped.append("(empty subject)")
            continue

        if norm in seen_subjects:
            logger.info(f"Skipping: '{subject}' - duplicate")
            skipped.append(f"{subject} (duplicate)")
            continue

        has_active_override = any(
            phrase in subject_lower or phrase in body
            for phrase in ACTIVE_OVERRIDE_PHRASES
        )

        if not has_active_override and any(phrase in subject_lower for phrase in SKIP_SUBJECT_PHRASES):
            logger.info(f"Skipping: '{subject}' - matched skip phrase")
            skipped.append(f"{subject} (expired/cancelled/trial)")
            continue

        if not has_active_override and any(phrase in body for phrase in EXPIRED_BODY_PHRASES):
            logger.info(f"Skipping: '{subject}' - expired/cancelled in body")
            skipped.append(f"{subject} (expired/cancelled in body)")
            continue

        logger.info(f"Keeping: '{subject}' from {sender}")
        seen_subjects.add(norm)
        kept.append(item)

    return kept, skipped


def _extract_price_from_text(text: str) -> tuple[float, str]:
    """Extract price and currency code from text using regex patterns.
    Returns (amount, currency_code) or (0.0, 'USD') if not found."""

    # Multi-currency patterns: symbol before amount
    for symbol, code in CURRENCY_SYMBOLS.items():
        escaped = re.escape(symbol)
        pattern = rf'{escaped}\s*(\d{{1,6}}(?:[.,]\d{{1,2}})?)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", ".")
            try:
                price = float(raw)
                if 1900 <= price <= 2100:
                    continue
                if price > 10000:
                    continue
                if price == 0:
                    continue
                return price, code
            except (ValueError, IndexError):
                continue

    # Amount followed by currency word
    word_patterns = [
        (r'(\d+\.?\d*)\s*(?:USD|dollars?)', "USD"),
        (r'(\d+\.?\d*)\s*(?:EUR|euros?)', "EUR"),
        (r'(\d+\.?\d*)\s*(?:GBP|pounds?)', "GBP"),
        (r'(\d+\.?\d*)\s*(?:GEL|lari)', "GEL"),
        (r'(\d+\.?\d*)\s*(?:TRY|lira)', "TRY"),
    ]
    for pattern, code in word_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                price = float(match.group(1))
                if 1900 <= price <= 2100 or price > 10000 or price == 0:
                    continue
                return price, code
            except (ValueError, IndexError):
                continue

    # Generic price/cost/amount phrases (default USD)
    generic_patterns = [
        r'(?:price|cost|amount|total|charged|charge)[:\s]+\$?(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*\/\s*(?:month|mo|year|yr)',
    ]
    for pattern in generic_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                price = float(match.group(1))
                if 1900 <= price <= 2100 or price > 10000 or price == 0:
                    continue
                return price, "USD"
            except (ValueError, IndexError):
                continue

    return 0.0, "USD"


def _extract_renewal_date_from_text(text: str) -> str | None:
    """Extract renewal/expiry date from email body/subject."""
    MONTHS = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09",
        "oct": "10", "nov": "11", "dec": "12",
    }

    m = re.search(r'\b(202\d)-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b', text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = re.search(r'\b(0?[1-9]|1[0-2])[/-]([0-2]?[1-9]|3[01])[/-](202\d)\b', text)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"

    m = re.search(
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december'
        r'|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2}),?\s+(202\d)\b',
        text, re.IGNORECASE
    )
    if m:
        month = MONTHS.get(m.group(1).lower(), "01")
        day = m.group(2).zfill(2)
        year = m.group(3)
        return f"{year}-{month}-{day}"

    m = re.search(
        r'\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december'
        r'|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec),?\s+(202\d)\b',
        text, re.IGNORECASE
    )
    if m:
        day = m.group(1).zfill(2)
        month = MONTHS.get(m.group(2).lower(), "01")
        year = m.group(3)
        return f"{year}-{month}-{day}"

    return None


def _default_renewal(cycle: str | None) -> str:
    today = date.today()
    if cycle and cycle.lower() == "yearly":
        return (today + timedelta(days=365)).isoformat()
    return (today + timedelta(days=30)).isoformat()


def rule_based_fallback(emails: list[dict]) -> list[dict]:
    results = []
    seen_names: set[str] = set()

    logger.info(f"Rule-based fallback processing {len(emails)} emails")

    for item in emails:
        subject = item.get("subject", "")
        body = item.get("body", "")
        sender = item.get("from", "").lower()
        subject_lower = subject.lower()
        if not any(h in subject_lower for h in SUBSCRIPTION_HINTS):
            logger.info(f"Skipping '{subject}' - no subscription hints")
            continue

        name = _guess_name_from_subject(subject, item.get("from", ""))
        key = name.lower()
        logger.info(f"Guessed name: '{name}' from subject '{subject}'")

        if name.lower() in ("unknown",) or name.lower() in GENERIC_SENDER_DOMAINS:
            logger.info(f"Skipping '{name}' - generic/unknown name")
            continue

        cost, currency = _extract_price_from_text(body)
        if cost == 0.0:
            cost, currency = _extract_price_from_text(subject)

        is_known_brand = any(brand in name.lower() for brand in KNOWN_SUBSCRIPTION_BRANDS)
        logger.info(f"Extracted cost: {cost} {currency}, is_known_brand: {is_known_brand}")

        if cost == 0.0:
            logger.info(f"Skipping '{name}' - no price found")
            continue

        if key in seen_names:
            logger.info(f"Skipping '{name}' - duplicate")
            continue
        seen_names.add(key)

        cycle = "Yearly" if "year" in subject_lower or "yearly" in body.lower() else "Monthly"

        renewal_date = (
            _extract_renewal_date_from_text(body)
            or _extract_renewal_date_from_text(subject)
            or _default_renewal(cycle)
        )

        confidence = _compute_confidence(name, cost, renewal_date, subject, body)
        logger.info(f"Adding '{name}' {cost} {currency} renewal={renewal_date} confidence={confidence}")
        results.append({
            "name": name,
            "cost": cost,
            "currency": currency,
            "cycle": cycle,
            "renewal_date": renewal_date,
            "method": _method_from_sender(item.get("from", "")),
            "confidence": confidence,
            "category": categorize_subscription(name),
        })

    logger.info(f"Rule-based fallback returned {len(results)} results")
    return results


def _guess_name_from_subject(subject: str, sender: str) -> str:
    subject_lower = subject.lower()
    sender_lower = sender.lower()

    for brand in KNOWN_SUBSCRIPTION_BRANDS:
        if brand in subject_lower or brand in sender_lower:
            return brand.capitalize()

    if "@" in sender_lower:
        domain = sender_lower.split("@")[-1].split(">")[0].split(".")[0]
        for brand in KNOWN_SUBSCRIPTION_BRANDS:
            if brand in domain:
                return brand.capitalize()
        if domain not in GENERIC_SENDER_DOMAINS:
            return domain.capitalize()

    words = subject.split()
    for word in words:
        word_clean = re.sub(r"[^\w]", "", word).lower()
        if len(word_clean) > 3 and word_clean not in GENERIC_SENDER_DOMAINS:
            for brand in KNOWN_SUBSCRIPTION_BRANDS:
                if brand in word_clean:
                    return brand.capitalize()
            return word_clean.capitalize()

    return "Unknown"


def _method_from_sender(sender: str) -> str:
    sender_lower = sender.lower()
    if "paypal" in sender_lower:
        return "PayPal"
    if "google" in sender_lower:
        return "Google Pay"
    if "apple" in sender_lower:
        return "Apple Pay"
    return "Gmail detected"


def _normalize_subscription(entry: dict, raw_email: dict | None = None) -> dict | None:
    """Normalise one AI-returned entry, then recompute confidence from signals
    so the LLM can never flat-line everything at a single value."""
    name = (entry.get("name") or "").strip()
    if not name or len(name) < 2:
        return None

    generic_names = ("gmail", "email", "updates", "announce", "notification",
                     "blogger", "redditmail", "google", "unknown")
    if name.lower() in generic_names:
        return None

    cost = entry.get("cost")
    try:
        cost = float(cost) if cost is not None else 0.0
    except (TypeError, ValueError):
        cost = 0.0
    if cost < 0:
        cost = 0.0
    if cost > 10000:
        return None
    if 1900 <= cost <= 2100:
        return None
    if cost == 0.0:
        return None

    currency = (entry.get("currency") or "USD").strip().upper()
    if len(currency) != 3:
        currency = "USD"

    cycle = entry.get("cycle") or "Monthly"
    if cycle not in ("Monthly", "Yearly"):
        cycle = "Monthly"

    renewal = entry.get("renewal_date")
    if renewal and re.match(r"^\d{4}-\d{2}-\d{2}$", str(renewal)):
        pass
    else:
        extracted = _extract_renewal_date_from_text(str(renewal or ""))
        renewal = extracted or _default_renewal(cycle)

    method = (entry.get("method") or "Gmail detected").strip() or "Gmail detected"

    # Read the LLM's raw hint, then override with our signal-based scorer
    ai_hint = entry.get("confidence")
    try:
        ai_hint = int(ai_hint) if ai_hint is not None else None
    except (TypeError, ValueError):
        ai_hint = None

    # Use the raw email body/subject if provided, else fall back to name only
    subject = (raw_email or {}).get("subject", name)
    body    = (raw_email or {}).get("body", "")
    confidence = _compute_confidence(name, cost, renewal, subject, body, ai_hint)

    category = (entry.get("category") or categorize_subscription(name)).strip()

    return {
        "name": name[:80],
        "cost": cost,
        "currency": currency,
        "cycle": cycle,
        "renewal_date": renewal,
        "method": method[:80],
        "confidence": confidence,
        "category": category,
    }


def analyze_with_ai(emails: list[dict]) -> list[dict]:
    if not emails:
        return []

    lines = []
    for i, item in enumerate(emails[:30], 1):
        body_preview = item.get("body", "")[:1500].replace("\n", " ")
        lines.append(
            f'{i}. Subject: "{item.get("subject", "")}" | From: {item.get("from", "unknown")} | Date: {item.get("date", "")} | Body: "{body_preview}"'
        )

    system = (
        "You identify ACTIVE RECURRING subscription services from emails. "
        "Return ONLY a valid JSON array, no markdown fences, no extra text. "
        "Exclude: one-time purchases, game receipts, failed payments, refunds, trials, free trials, "
        "marketing/promotional emails, newsletters, subscription ended/cancelled notices. "
        "Only include ACTIVE subscriptions with an ACTUAL PRICE found in the email. "
        "Always try to extract the renewal/next billing date from the email body. "
        "If no price is found, DO NOT include the entry. "
        "If no renewal date is found, set renewal_date to null. "
        "Include currency as ISO 3-letter code (USD, EUR, GBP, GEL, TRY, JPY, etc). "
        "Include category: Streaming, Music, Gaming, Productivity, AI Tools, Design, Security, Cloud, Learning, Social, or Other. "
        "Include a confidence field (integer 0-100): use a DIFFERENT value for each entry based on "
        "how much evidence you see — a clear payment receipt with invoice number and date should be "
        "90+, a vague renewal notice with no invoice should be 55-70, marketing with a price mentioned "
        "should be 40-55. Do NOT output the same number for multiple entries."
    )
    prompt = f"""Analyze these emails. Return a JSON array of ACTIVE recurring subscriptions only.

Each object must have exactly these fields:
{{"name":"Service Name","cost":9.99,"currency":"USD","cycle":"Monthly" or "Yearly","renewal_date":"YYYY-MM-DD" or null,"method":"payment method or null","confidence":85,"category":"Streaming"}}

Rules:
- cost must be a real number > 0 found in the email. If missing, skip the entry.
- renewal_date: extract from "renews on", "next billing date", "your next payment", "charged on". YYYY-MM-DD or null.
- confidence: vary this per entry — a clear invoice = 90+, ambiguous renewal notice = 65, vague mention = 50.
- Exclude: trials, cancelled, ended, failed, refunded, one-time, marketing, newsletters.

Emails to analyze:
{chr(10).join(lines)}"""

    try:
        raw = ask_groq(prompt, system=system)
        logger.info(f"AI raw response: {raw[:500]}")
        parsed = _extract_json_array(raw)
        logger.info(f"AI parsed {len(parsed)} entries")
    except Exception as exc:
        logger.warning(f"AI analysis failed: {exc}, using rule-based fallback")
        return rule_based_fallback(emails)

    # Build a subject→email lookup so _normalize_subscription can use body signals
    email_by_subject: dict[str, dict] = {}
    for em in emails:
        subj = (em.get("subject") or "").strip().lower()
        if subj:
            email_by_subject[subj] = em

    results = []
    seen: set[str] = set()
    for entry in parsed:
        logger.info(f"Processing AI entry: {entry}")
        if entry.get("is_subscription") is False:
            continue

        # Try to match the AI entry back to the original email for signal scoring
        matched_email = email_by_subject.get((entry.get("name") or "").lower())
        # Fallback: search by name fragment
        if not matched_email:
            name_lower = (entry.get("name") or "").lower()
            for em in emails:
                if name_lower in (em.get("subject") or "").lower() or \
                   name_lower in (em.get("from") or "").lower():
                    matched_email = em
                    break

        normalized = _normalize_subscription(entry, raw_email=matched_email)
        if not normalized:
            logger.info(f"Skipping - normalization returned None for: {entry}")
            continue
        key = normalized["name"].lower()
        if key in seen:
            logger.info(f"Skipping duplicate: {key}")
            continue
        seen.add(key)
        logger.info(
            f"Adding: {normalized['name']} {normalized['cost']} {normalized['currency']} "
            f"confidence={normalized['confidence']} renewal={normalized['renewal_date']}"
        )
        results.append(normalized)

    logger.info(f"AI analysis returned {len(results)} valid subscriptions")
    return results if results else rule_based_fallback(emails)


def dedupe_subscriptions(subs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for sub in subs:
        key = sub["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(sub)
    return out
