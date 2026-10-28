"""Tests for categorizing notification email preferences."""

from arm.ripper.utils import _email_notification_category


def test_error_notifications_take_priority_over_completion_wording():
    assert _email_notification_category(
        "ARM notification", "Processing completed with errors; titles failed to complete."
    ) == "error"


def test_successful_rip_completion_is_classified_as_completion():
    assert _email_notification_category(
        "ARM notification", "The Matrix rip complete. Starting transcode."
    ) == "completion"


def test_copy_completion_is_classified_as_completion():
    assert _email_notification_category(
        "ARM notification", "Data disc: archive copying complete."
    ) == "completion"


def test_disc_detection_is_classified_as_other():
    assert _email_notification_category(
        "ARM notification", "Found disc: The Matrix. Disc type is bluray."
    ) == "other"
