from services.subscription_detector import detect_subscription

def scan_emails(email_list):

    detected_subscriptions = []

    for email in email_list:

        result = detect_subscription(email)

        if result["is_subscription"]:

            detected_subscriptions.append({
                "email": email,
                "services": result["services"]
            })

    return detected_subscriptions