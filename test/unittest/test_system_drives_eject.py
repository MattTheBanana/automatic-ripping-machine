"""Regression tests for optical-drive eject command failures."""

from subprocess import CalledProcessError
from types import SimpleNamespace
from unittest.mock import patch

from arm.models.system_drives import SystemDrives


def test_eject_returns_combined_output_on_command_failure():
    drive = SimpleNamespace(mount="/dev/sr0")
    failure = CalledProcessError(
        1, ["eject", "/dev/sr0"],
        output="eject: cannot open /dev/sr0: Device or resource busy",
    )

    with patch("arm.models.system_drives.arm_subprocess", side_effect=failure):
        error = SystemDrives.eject(drive)

    assert "Device or resource busy" in error


def test_eject_returns_os_error_when_command_cannot_run():
    drive = SimpleNamespace(mount="/dev/sr0")

    with patch(
        "arm.models.system_drives.arm_subprocess",
        side_effect=FileNotFoundError("eject executable not found"),
    ):
        error = SystemDrives.eject(drive)

    assert "eject executable not found" in error


def test_default_eject_allows_cdrom_and_scsi_methods():
    drive = SimpleNamespace(mount="/dev/sr0")

    with patch("arm.models.system_drives.arm_subprocess") as run:
        SystemDrives.eject(drive)

    command = run.call_args.args[0]
    assert "--cdrom" in command
    assert "--scsi" in command
    assert "--traytoggle" not in command


def test_close_method_uses_explicit_tray_close():
    drive = SimpleNamespace(mount="/dev/sr0")

    with patch("arm.models.system_drives.arm_subprocess") as run:
        SystemDrives.eject(drive, method="close")

    command = run.call_args.args[0]
    assert "--trayclose" in command
    assert "--traytoggle" not in command
