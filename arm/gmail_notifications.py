"""Gmail API notifications using a stored Google OAuth refresh token.

No Google SDK dependency is required. The refresh token is exchanged for a
short-lived access token, and messages are sent with the narrow gmail.send scope.
"""
import base64
import logging
import re
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr

import requests


LOGGER = logging.getLogger(__name__)
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
REQUIRED_SETTINGS = (
    "GMAIL_OAUTH_CLIENT_ID",
    "GMAIL_OAUTH_CLIENT_SECRET",
    "GMAIL_OAUTH_REFRESH_TOKEN",
    "GMAIL_SENDER_EMAIL",
    "GMAIL_RECIPIENTS",
)


def _email_address(value):
    """Return a basic email address or an empty string for invalid input."""
    display_name, address = parseaddr(str(value or "").strip())
    if not display_name and "@" not in address:
        return ""
    if not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", address):
        return ""
    return address


def _recipients(value):
    """Parse a comma- or semicolon-separated list of recipient addresses."""
    entries = re.split(r"[,;]", str(value or ""))
    addresses = [address for _, address in getaddresses(entries) if address]
    valid = [_email_address(address) for address in addresses]
    return list(dict.fromkeys(address for address in valid if address))


def send_gmail_notification(title, body, config=None, http_client=None):
    """Send a plain-text notification through Gmail API using OAuth 2.0.

    Return True if Gmail accepts the message. Empty Gmail settings disable this
    notifier; partial/invalid settings and delivery failures are logged and
    return False. Existing notification providers are unaffected by failures.
    """
    if config is None:
        from arm.config import config as arm_config
        config = arm_config.arm_config
    if http_client is None:
        http_client = requests

    values = {key: str(config.get(key) or "").strip() for key in REQUIRED_SETTINGS}
    if not any(values.values()):
        return False
    missing = [key for key, value in values.items() if not value]
    if missing:
        LOGGER.warning("Gmail OAuth notifications are not configured; missing %s", ", ".join(missing))
        return False

    sender = _email_address(values["GMAIL_SENDER_EMAIL"])
    recipients = _recipients(values["GMAIL_RECIPIENTS"])
    if not sender:
        LOGGER.warning("Gmail OAuth notifications not sent: GMAIL_SENDER_EMAIL is not a valid email address")
        return False
    if not recipients:
        LOGGER.warning("Gmail OAuth notifications not sent: GMAIL_RECIPIENTS has no valid email addresses")
        return False

    # Keep user-supplied title text from introducing extra MIME headers.
    safe_subject = re.sub(r"[\r\n]+", " ", str(title or "")).strip() or "ARM notification"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = safe_subject[:250]
    message.set_content(str(body or ""))
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    try:
        token_response = http_client.post(
            TOKEN_URL,
            data={
                "client_id": values["GMAIL_OAUTH_CLIENT_ID"],
                "client_secret": values["GMAIL_OAUTH_CLIENT_SECRET"],
                "refresh_token": values["GMAIL_OAUTH_REFRESH_TOKEN"],
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        token_response.raise_for_status()
        token = token_response.json().get("access_token")
        if not token:
            LOGGER.warning("Gmail OAuth token refresh returned no access token")
            return False

        send_response = http_client.post(
            SEND_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"raw": raw_message},
            timeout=15,
        )
        send_response.raise_for_status()
    except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
        LOGGER.warning("Gmail OAuth notification delivery failed: %s", error)
        return False

    LOGGER.info("Gmail notification accepted for %d recipient(s)", len(recipients))
    return True
