import unittest
from unittest.mock import MagicMock, patch

from arm.smtp_notifications import send_smtp_notification


CONFIG = {
    "EMAIL_NOTIFICATION_METHOD": "smtp",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": 587,
    "SMTP_USERNAME": "arm-sender@example.com",
    "SMTP_PASSWORD": "provider-app-password",
    "SMTP_SENDER_EMAIL": "arm-sender@example.com",
    "SMTP_RECIPIENTS": "viewer@example.com; backup@example.com",
    "SMTP_USE_TLS": True,
    "SMTP_USE_SSL": False,
}


class TestSmtpNotifications(unittest.TestCase):
    def setUp(self):
        self.smtp = MagicMock()
        self.smtp.__enter__.return_value = self.smtp
        self.smtp.__exit__.return_value = False
        self.factory = MagicMock(return_value=self.smtp)

    @patch("arm.smtp_notifications.ssl.create_default_context")
    def test_sends_email_using_starttls_and_app_password(self, ssl_context):
        self.smtp.send_message.return_value = {}
        sent = send_smtp_notification(
            "ARM finished", "Disc ripped.", CONFIG, smtp_factory=self.factory
        )
        self.assertTrue(sent)
        self.factory.assert_called_once_with("smtp.example.com", 587, timeout=15)
        self.smtp.starttls.assert_called_once_with(context=ssl_context.return_value)
        self.smtp.login.assert_called_once_with("arm-sender@example.com", "provider-app-password")
        message = self.smtp.send_message.call_args.args[0]
        self.assertEqual(message["From"], "arm-sender@example.com")
        self.assertEqual(message["To"], "viewer@example.com, backup@example.com")
        self.assertEqual(message["Subject"], "ARM finished")
        self.assertIn("Disc ripped.", message.get_content())

    def test_unselected_smtp_transport_does_not_send(self):
        config = dict(CONFIG, EMAIL_NOTIFICATION_METHOD="gmail_oauth")
        self.assertFalse(send_smtp_notification("Test", "Body", config, smtp_factory=self.factory))
        self.factory.assert_not_called()

    def test_unconfigured_smtp_is_disabled(self):
        config = {"EMAIL_NOTIFICATION_METHOD": "smtp", "SMTP_PORT": 587, "SMTP_USE_TLS": True}
        self.assertFalse(send_smtp_notification("Test", "Body", config, smtp_factory=self.factory))
        self.factory.assert_not_called()

    def test_username_without_password_fails_closed(self):
        config = dict(CONFIG, SMTP_PASSWORD="")
        self.assertFalse(send_smtp_notification("Test", "Body", config, smtp_factory=self.factory))
        self.factory.assert_not_called()

    def test_invalid_port_fails_closed(self):
        config = dict(CONFIG, SMTP_PORT="not-a-port")
        self.assertFalse(send_smtp_notification("Test", "Body", config, smtp_factory=self.factory))
        self.factory.assert_not_called()

    @patch("arm.smtp_notifications.ssl.create_default_context")
    def test_supports_implicit_tls(self, ssl_context):
        config = dict(CONFIG, SMTP_USE_TLS=False, SMTP_USE_SSL=True, SMTP_PORT=465)
        self.smtp.send_message.return_value = {}
        sent = send_smtp_notification(
            "Test", "Body", config, smtp_ssl_factory=self.factory
        )
        self.assertTrue(sent)
        self.factory.assert_called_once_with(
            "smtp.example.com", 465, timeout=15, context=ssl_context.return_value
        )
        self.smtp.starttls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
