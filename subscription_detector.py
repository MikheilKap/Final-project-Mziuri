SUBSCRIPTION_KEYWORDS = [
    "subscription",
    "invoice",
    "payment",
    "renewal",
    "receipt",
    "premium",
    "monthly plan"
]

KNOWN_SERVICES = [
    "Netflix",
    "Spotify",
    "Adobe",
    "Amazon Prime",
    "Disney+",
    "YouTube Premium"
]

def detect_subscription(email_text):

    text = email_text.lower()

    found_keywords = []

    for keyword in SUBSCRIPTION_KEYWORDS:

        if keyword.lower() in text:
            found_keywords.append(keyword)

    detected_services = []

    for service in KNOWN_SERVICES:

        if service.lower() in text:
            detected_services.append(service)

    return {
        "is_subscription": len(found_keywords) > 0,
        "keywords": found_keywords,
        "services": detected_services
    }
 