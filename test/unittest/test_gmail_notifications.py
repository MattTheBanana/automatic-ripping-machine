import base64
import unittest
from unittest.mock import Mock, patch

import requests

from arm.gmail_notifications import SEND_URL, TOKEN_URL, send_gmail_notification


CONFIG = {
    "GMAIL_OAUTH_CLIENT_ID": "client-id",
    "GMAIL_OAUTH_CLIENT_SECRET": "client-secret",
    "GMAIL_OAUTH_REFRESH_TOKEN": "refresh-token",
    "GMAIL_SENDER_EMAIL": "arm-sender@example.com",
    "GMAIL_RECIPIENTS": "viewer@example.com; backup@example.com",
}


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class TestGmailOAuthNotifications(unittest.TestCase):
    @patch("arm.gmail_notifications.requests.post")
    def test_sends_message_after_refreshing_access_token(self, post):
        post.side_effect = [
            FakeResponse({"access_token": "short-lived-token"}),
            FakeResponse({"id": "message-123"}),
        ]

        self.assertTrue(send_gmail_notification("ARM finished", "Disc ripped.", CONFIG))
        self.assertEqual(post.call_count, 2)
        token_call = post.call_args_list[0]
        self.assertEqual(token_call.args[0], TOKEN_URL)
        self.assertEqual(token_call.kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(token_call.kwargs["data"]["refresh_token"], "refresh-token")

        send_call = post.call_args_list[1]
        self.assertEqual(send_call.args[0], SEND_URL)
        self.assertEqual(send_call.kwargs["headers"]["Authorization"], "Bearer short-lived-token")
        raw = send_call.kwargs["json"]["raw"]
        message_bytes = base64.urlsafe_b64decode(raw.encode("ascii"))
        self.assertIn(b"To: viewer@example.com, backup@example.com", message_bytes)
        self.assertIn(b"Subject: ARM finished", message_bytes)
        self.assertIn(b"Disc ripped.", message_bytes)

    @patch("arm.gmail_notifications.requests.post")
    def test_all_blank_settings_disable_gmail_without_network_calls(self, post):
        empty = {key: "" for key in CONFIG}
        self.assertFalse(send_gmail_notification("Test", "Body", empty))
        post.assert_not_called()

    @patch("arm.gmail_notifications.requests.post")
    def test_missing_credentials_fail_closed(self, post):
        incomplete = dict(CONFIG)
        incomplete["GMAIL_OAUTH_REFRESH_TOKEN"] = ""
        self.assertFalse(send_gmail_notification("Test", "Body", incomplete))
        post.assert_not_called()

    @patch("arm.gmail_notifications.requests.post")
    def test_oauth_error_does_not_send_message(self, post):
        post.side_effect = [FakeResponse(status_code=401)]
        self.assertFalse(send_gmail_notification("Test", "Body", CONFIG))
        self.assertEqual(post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
