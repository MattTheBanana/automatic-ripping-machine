"""Regression tests for missing optical-drive inventory and rip diagnostics."""

from pathlib import Path
import unittest
from unittest.mock import patch

from arm.ui.settings import DriveUtils


ROOT = Path(__file__).resolve().parents[2]


class TestOpticalDriveInventory(unittest.TestCase):
    def test_drive_nodes_missing_from_udev_are_discovered(self):
        with patch.object(DriveUtils.pyudev, "Context") as context_factory:
            with patch.object(DriveUtils.glob, "glob", return_value=["/dev/sr3"]):
                context_factory.return_value.list_devices.return_value = []
                drives = list(DriveUtils.drives_search())

        self.assertEqual(len(drives), 1)
        self.assertEqual(drives[0].mount, "/dev/sr3")
        self.assertEqual(drives[0].serial_id, "")
        self.assertEqual(drives[0].model, "Optical drive")

    def test_drive_with_missing_serial_is_matched_by_mount(self):
        source = (ROOT / "arm/ui/settings/DriveUtils.py").read_text(encoding="utf-8")

        self.assertIn("if drive.serial_id:", source)
        self.assertIn(
            'SystemDrives.query.filter_by(mount=drive.mount).first()',
            source,
        )
        self.assertIn(
            "Do not match multiple metadata-poor fallback devices by an empty serial.",
            source,
        )
        self.assertIn("if is_fallback and not is_new_drive:", source)

    def test_ripper_refreshes_drive_inventory_before_reporting_missing_drive(self):
        source = (ROOT / "arm/ripper/main.py").read_text(encoding="utf-8")

        self.assertIn("drive_utils.drives_update()", source)
        self.assertIn("is missing from ARM's drive inventory after refresh", source)
        self.assertNotIn(
            "SystemDrives.query.filter_by(mount=devpath).one()",
            source,
        )

    def test_makemkv_failure_logs_underlying_exception_and_output(self):
        ripper_source = (ROOT / "arm/ripper/arm_ripper.py").read_text(encoding="utf-8")
        makemkv_source = (ROOT / "arm/ripper/makemkv.py").read_text(encoding="utf-8")

        self.assertIn("MakeMKV failed for %s (%s): %s", ripper_source)
        self.assertIn("MakeMKV output before failure", makemkv_source)


if __name__ == "__main__":
    unittest.main()
