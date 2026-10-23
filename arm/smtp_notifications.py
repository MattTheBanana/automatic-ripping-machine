"""Send ARM email notifications through a configurable SMTP server."""

import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr


LOGGER = logging.getLogger(__name__)
REQUIRED_SETTINGS = ("SMTP_HOST", "SMTP_PORT", "SMTP_SENDER_EMAIL", "SMTP_RECIPIENTS")


def _email_address(value):
    """Return a basic email address or an empty string when invalid."""
    _, address = parseaddr(str(value or "").strip())
    if not re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", address):
        return ""
    return address


def _recipients(value):
    """Parse and de-duplicate comma- or semicolon-separated recipients."""
    entries = re.split(r"[,;]", str(value or ""))
    recipients = []
    for _, candidate in getaddresses(entries):
        address = _email_address(candidate)
        if address and address not in recipients:
            recipients.append(address)
    return recipients


def _as_bool(value, default=False):
    """Parse a boolean from YAML or a settings form."""
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def send_smtp_notification(title, body, config=None, smtp_factory=None, smtp_ssl_factory=None):
    """Send email through SMTP when EMAIL_NOTIFICATION_METHOD is smtp.

    STARTTLS is enabled by default. SMTP_USE_SSL selects implicit TLS instead;
    the two TLS modes are mutually exclusive.

    Returns True only when the server accepts the message. Missing settings
    disable delivery, and failures are isolated from ripping.
    """
    if config is None:
        from arm.config import config as arm_config
        config = arm_config.arm_config

    method = str(config.get("EMAIL_NOTIFICATION_METHOD", "gmail_oauth")).strip().lower()
    if method != "smtp":
        return False

    values = {
        "SMTP_HOST": str(config.get("SMTP_HOST") or "").strip(),
        "SMTP_PORT": str(config.get("SMTP_PORT") or "587").strip(),
        "SMTP_USERNAME": str(config.get("SMTP_USERNAME") or "").strip(),
        "SMTP_PASSWORD": str(config.get("SMTP_PASSWORD") or "").strip(),
        "SMTP_SENDER_EMAIL": str(config.get("SMTP_SENDER_EMAIL") or "").strip(),
        "SMTP_RECIPIENTS": str(config.get("SMTP_RECIPIENTS") or "").strip(),
    }

    # Avoid log spam while a newly selected transport is not configured yet.
    if not any(values[key] for key in (
        "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD",
        "SMTP_SENDER_EMAIL", "SMTP_RECIPIENTS",
    )):
        return False

    missing = [key for key in REQUIRED_SETTINGS if not values[key]]
    if missing:
        LOGGER.warning("SMTP notifications are missing settings: %s", ", ".join(missing))
        return False

    if bool(values["SMTP_USERNAME"]) != bool(values["SMTP_PASSWORD"]):
        LOGGER.warning("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        return False

    sender = _email_address(values["SMTP_SENDER_EMAIL"])
    recipients = _recipients(values["SMTP_RECIPIENTS"])
    if not sender or not recipients:
        LOGGER.warning("SMTP notifications require a valid sender and at least one recipient")
        return False

    try:
        port = int(values["SMTP_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError("SMTP port is out of range")
    except (TypeError, ValueError):
        LOGGER.warning("SMTP_PORT must be a valid TCP port")
        return False

    use_tls = _as_bool(config.get("SMTP_USE_TLS", True), default=True)
    use_ssl = _as_bool(config.get("SMTP_USE_SSL", False))
    if use_tls and use_ssl:
        LOGGER.warning("Choose either SMTP_USE_TLS or SMTP_USE_SSL, not both")
        return False

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = re.sub(r"[\r\n]+", " ", str(title or "ARM notification"))
    message.set_content(str(body or ""))

    smtp_factory = smtp_factory or smtplib.SMTP
    smtp_ssl_factory = smtp_ssl_factory or smtplib.SMTP_SSL
    try:
        if use_ssl:
            with smtp_ssl_factory(
                values["SMTP_HOST"], port, timeout=15, context=ssl.create_default_context()
            ) as smtp:
                if values["SMTP_USERNAME"]:
                    smtp.login(values["SMTP_USERNAME"], values["SMTP_PASSWORD"])
                refused = smtp.send_message(message)
        else:
            with smtp_factory(values["SMTP_HOST"], port, timeout=15) as smtp:
                if use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                if values["SMTP_USERNAME"]:
                    smtp.login(values["SMTP_USERNAME"], values["SMTP_PASSWORD"])
                refused = smtp.send_message(message)
    except (smtplib.SMTPException, OSError, ValueError, TypeError, AttributeError) as error:
        LOGGER.warning("SMTP notification failed (%s)", type(error).__name__)
        return False

    if refused:
        LOGGER.warning("SMTP server refused one or more recipients")
        return False

    LOGGER.info("SMTP notification sent to %d recipient(s)", len(recipients))
    return True
