import os
import sys

import requests

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
FROM_ADDRESS = os.environ.get("NOTIFY_FROM_ADDRESS", "onboarding@resend.dev")


def send_email(to_email, subject, body_text):
    if not RESEND_API_KEY:
        return
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": FROM_ADDRESS,
                "to": [to_email],
                "subject": subject,
                "text": body_text,
            },
            timeout=5,
        )
        if not response.ok:
            print(
                f"notifications: Resend rejected email to {to_email}: "
                f"{response.status_code} {response.text}",
                file=sys.stderr,
            )
    except requests.RequestException as e:
        print(f"notifications: failed to send email to {to_email}: {e}", file=sys.stderr)
