import os
import smtplib
import sys
from email.mime.text import MIMEText

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


def send_email(to_email, subject, body_text):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return

    msg = MIMEText(body_text)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, [to_email], msg.as_string())
    except smtplib.SMTPException as e:
        print(f"notifications: failed to send email to {to_email}: {e}", file=sys.stderr)
