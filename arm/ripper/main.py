#!/usr/bin/env python3
"""
The main runner for Automatic Ripping Machine

For help please visit https://github.com/automatic-ripping-machine/automatic-ripping-machine
"""
import argparse  # noqa: E402
import logging  # noqa: E402
import sys
import time  # noqa: E402
import datetime  # noqa: E402
import re  # noqa: E402
from argparse import Namespace
from importlib.util import find_spec
from pathlib import Path
from signal import signal, SIGTERM
from typing import Optional

import pyudev  # noqa: E402

# If the arm module can't be found, add the folder this file is in to PYTHONPATH
# This is a bad workaround for non-existent packaging
if find_spec("arm") is None:
    sys.path.append(str(Path(__file__).parents[2]))

import arm.config.config as cfg  # noqa E402
from arm.models.config import Config  # noqa: E402
from arm.models.job import Job, JobState  # noqa: E402
from arm.models.system_drives import SystemDrives  # noqa: E402
from arm.ripper import (arm_ripper, identify, logger,  # noqa: E402
                        music_brainz, utils)
from arm.ripper.ARMInfo import ARMInfo  # noqa E402
from arm.ui import app, constants, db  # noqa E402
from arm.ui.settings import DriveUtils as drive_utils  # noqa E402

job: Optional[Job] = None
args: Optional[Namespace] = None
log_file: Optional[str] = None
_job_registered = False


def entry():
    """ Entry to program, parses arguments"""
    parser = argparse.ArgumentParser(description='Process disc using ARM')
    parser.add_argument('-d', '--devpath', help='Devpath', required=True)
    parser.add_argument(
        "--syslog",
        help="Log to /dev/log",
        required=False,
        default=True,
        action=argparse.BooleanOptionalAction,
    )
    return parser.parse_args()


def log_udev_params(dev_path):
    """log all udev parameters"""

    logging.debug("******************* Logging udev attributes *******************")
    context = pyudev.Context()
    device = pyudev.Devices.from_device_file(context, dev_path)
    for key, value in device.items():
        logging.debug(f"{key}:{value}")
    logging.debug("******************* End udev attributes *******************")


def log_arm_params(job):
    """log all entry parameters"""

    # log arm parameters
    logging.info("******************* Logging ARM variables *******************")
    for key in ("devpath", "mountpoint", "title", "year", "video_type",
                "hasnicetitle", "label", "disctype", "manual_start"):
        logging.info(f"{key}: {str(getattr(job, key))}")
    logging.info("******************* End of ARM variables *******************")
    logging.info("******************* Logging config parameters *******************")
    for key in ("SKIP_TRANSCODE", "MAINFEATURE", "MINLENGTH", "MAXLENGTH",
                "VIDEOTYPE", "MANUAL_WAIT", "MANUAL_WAIT_TIME", "RIPMETHOD",
                "MKV_ARGS", "DELRAWFILES", "HB_PRESET_DVD", "HB_PRESET_BD",
                "HB_ARGS_DVD", "HB_ARGS_BD", "FFMPEG_CLI", "FFMPEG_LOCAL", "USE_FFMPEG",
                "FFMPEG_ARGS", "RAW_PATH", "TRANSCODE_PATH",
                "COMPLETED_PATH", "EXTRAS_SUB", "EMBY_REFRESH", "EMBY_SERVER",
                "EMBY_PORT", "NOTIFY_RIP", "NOTIFY_TRANSCODE",
                "MAX_CONCURRENT_TRANSCODES", "MAX_CONCURRENT_MAKEMKVINFO"):
        logging.info(f"{key.lower()}: {str(cfg.arm_config.get(key, '<not given>'))}")
    logging.info("******************* End of config parameters *******************")


def check_fstab():
    """
    Check the fstab entries to see if ARM has been set up correctly
    :return: None

    # todo: remove this from the ripper and add into the ARM UI with a warning
    """
    logging.info("Checking for fstab entry.")
    try:
        with open('/etc/fstab', 'r') as fstab:
            lines = fstab.readlines()
    except OSError as error:
        logging.warning(f"Could not read /etc/fstab ({error}). Skipping fstab check.")
        return
    for line in lines:
        # Now grabs the real uncommented fstab entry
        if re.search("^" + re.escape(job.devpath), line):
            logging.info(f"fstab entry is: {line.rstrip()}")
            return
    logging.error("No fstab entry found.  ARM will likely fail.")


def main():
    """main disc processing function"""
    logging.info("Starting Disc identification")
    identify.identify(job)

    # Check db for entries matching the crc and successful
    have_dupes = utils.job_dupe_check(job)
    logging.debug(f"Value of have_dupes: {have_dupes}")

    utils.notify_entry(job)
    # Check if user has manual wait time enabled
    utils.check_for_wait(job)

    log_arm_params(job)
    check_fstab()

    # Ripper type assessment for the various media types
    # Type: dvd/bluray
    if job.disctype in ["dvd", "bluray"]:
        # Monitor only the period when ARM is reading the disc directly. If
        # MakeMKV has already copied the data to disk, the subsequent transcode
        # must not produce a false drive-sleep alert.
        direct_drive_source = not arm_ripper.rip_with_mkv(job, job.has_track_99)
        drive_watchdog = utils.DriveSleepWatchdog(
            job, direct_drive_source=direct_drive_source
        )
        drive_watchdog.start()
        try:
            arm_ripper.rip_visual_media(have_dupes, job, log_file, job.has_track_99)
        finally:
            drive_watchdog.stop()

    # Type: Music
    elif job.disctype == "music":
        # Identify the disc, then monitor the physical CD read while abcde is active.
        music_brainz.main(job)
        drive_watchdog = utils.DriveSleepWatchdog(job, direct_drive_source=True)
        drive_watchdog.start()
        try:
            music_ripped = utils.rip_music(job, log_file)
        finally:
            drive_watchdog.stop()
        if music_ripped:
            utils.notify(job, constants.NOTIFY_TITLE, f"Music CD: {job.title} {constants.PROCESS_COMPLETE}")
            utils.scan_emby()
            # This shouldn't be needed. but to be safe
            job.status = JobState.SUCCESS.value
            db.session.commit()
        else:
            logging.critical("Music rip failed.  See previous errors.  Exiting. ")
            job.status = JobState.FAILURE.value
            db.session.commit()

    # Type: Data
    elif job.disctype == "data":
        logging.info("Disc identified as data")
        if utils.rip_data(job):
            utils.notify(job, constants.NOTIFY_TITLE, f"Data disc: {job.label} copying complete. ")
        else:
            logging.critical("Data rip failed.  See previous errors.  Exiting.")

    # Type: undefined
    else:
        logging.critical("Couldn't identify the disc type. Exiting without any action.")


def setup():
    global job
    global args
    global log_file
    global _job_registered

    _job_registered = False

    def signal_handler(_signal, _frame_type):
        abort_reason = getattr(job, "_arm_abort_reason", None) if job is not None else None
        raise utils.RipperException(abort_reason or "Received SIGTERM")

    # Handle SIGTERM so we can exit gracefully. Without this, no except: or finally: blocks are
    # run and the program exits immediately, potentially leaving the database in an invalid state.
    signal(SIGTERM, signal_handler)

    # Get arguments from arg parser
    args = entry()
    devpath = f"/dev/{args.devpath}"
    # Setup base logger - will log to <log directory>/arm.log, syslog & stdout
    # This will catch any permission errors
    arm_log = logger.create_early_logger(syslog=args.syslog)
    # Make sure all directories are fully setup
    utils.arm_setup(arm_log)
    drive = SystemDrives.query.filter_by(mount=devpath).one()  # unique mounts

    # Duplicate udev events are normal on some optical drives. Check before creating a
    # Job object so a second launch cannot produce a false failure or touch the tray.
    utils.duplicate_run_check(devpath)

    # With some drives and some disks, there is a race condition between creating the Job()
    # below and the drive being ready, so give it a chance to get ready (observed with LG SP80NB80)
    for num in range(1, 11):
        drive.tray_status()
        if drive.ready:
            break
        if drive.open:
            raise utils.DriveNotReadyException(
                f"Drive tray is open on {devpath}; no rip was started."
            )
        msg = f"[{num} of 10] Drive [{drive.mount}] appears to be empty or is not ready. Waiting 1s"
        logging.info(msg)
        time.sleep(1)
    else:  # no break
        drive.tray_status()
        if drive.open:
            raise utils.DriveNotReadyException(
                f"Drive tray is open on {devpath}; no rip was started."
            )
        raise utils.RipperException(
            f"Timed out waiting for drive to be ready (ioctl tray status: {drive.tray})."
        )

    # ARM Job starts
    # Create new job
    job = Job(devpath)
    # Setup logging
    log_file = logger.setup_job_log(job)

    # Capture and report the ARM Info
    arminfo = ARMInfo(cfg.arm_config["INSTALLPATH"], cfg.arm_config['DBFILE'])
    job.arm_version = arminfo.arm_version
    arminfo.get_values()

    logging.info(f"************* Starting ARM processing at {datetime.datetime.now()} *************")
    # Set job status and start time
    job.status = JobState.IDLE.value
    job.start_time = datetime.datetime.now()
    utils.database_adder(job)
    _job_registered = True
    # Sleep to lower chances of db locked - unlikely to be needed
    time.sleep(1)
    # Associate the job with the drive in the database
    drive_utils.update_drive_job(job)
    # Add the job.config to db
    config = Config(cfg.arm_config, job_id=job.job_id)  # noqa: F811
    # Check if the drive mode is set to manual, and load to the job config for later use
    logging.debug(f"drive_mode: {drive.drive_mode}")
    if drive.drive_mode == 'manual':
        job.manual_mode = True
        db.session.commit()
    else:
        job.manual_mode = False
        db.session.commit()
    utils.database_adder(config)

    try:
        # Delete old log files
        logger.clean_up_logs(cfg.arm_config["LOGPATH"], cfg.arm_config["LOGLIFE"])
    except Exception as error:
        logging.error(error, exc_info=True)

    logging.info(f"Job: {job.label}")  # This will sometimes be none
    # Check for zombie jobs and update status to 'failed'
    utils.clean_old_jobs()
    # Log all params/attribs from the drive
    log_udev_params(devpath)


if __name__ == "__main__":
    job = None
    _job_registered = False
    try:
        setup()
        main()
    except utils.DuplicateRunException as duplicate:
        # A second udev event is expected on some hardware; it isn't a failed rip.
        logging.getLogger("ARM").info("Ignoring duplicate optical-drive trigger: %s", duplicate)
    except utils.DriveNotReadyException as not_ready:
        # An open tray/no medium is an expected drive state, not a failed job.
        logging.getLogger("ARM").info("No rip started: %s", not_ready)
    except Exception as error:
        arm_logger = logging.getLogger("ARM")
        arm_logger.critical("A fatal error has occurred and ARM is exiting.")
        print_stacktrace = (
            arm_logger.getEffectiveLevel() == logging.DEBUG
            or not isinstance(error, utils.RipperException)
        )
        arm_logger.critical("%s", error, exc_info=(error if print_stacktrace else None))

        if job is not None and _job_registered:
            disc_context = job.title or job.label or job.devpath or f"Job {job.job_id}"
            abort_reason = getattr(job, "_arm_abort_reason", None)
            if abort_reason:
                notification_title = f"ARM job cancelled: {disc_context}"[:256]
                notification_body = utils.format_failure_notification(
                    disc_context, abort_reason, job.logfile or "arm.log", outcome="Job cancelled"
                )
            else:
                notification_title = f"ARM job failed: {disc_context}"[:256]
                notification_body = utils.format_failure_notification(
                    disc_context, error, job.logfile or "arm.log"
                )
            utils.notify(job, notification_title, notification_body)
            job.status = JobState.FAILURE.value
            job.errors = abort_reason or str(error)
        else:
            device_path = (
                f"/dev/{args.devpath}" if args and getattr(args, "devpath", None)
                else "unknown drive"
            )
            notification_title = f"ARM job setup failed: {device_path}"[:256]
            notification_body = utils.format_failure_notification(
                device_path, error, "arm.log", setup=True
            )
            utils.notify(None, notification_title, notification_body)
    else:
        if job is not None and _job_registered:
            job.status = JobState.SUCCESS.value
    finally:
        # Only finalize jobs that were actually inserted into the database. In particular,
        # duplicate udev triggers must never eject or finalize an active job's disc.
        if job is not None and _job_registered:
            job.eject()
            job.stop_time = datetime.datetime.now()
            if job.start_time:
                job_length = job.stop_time - job.start_time
                minutes, seconds = divmod(job_length.seconds + job_length.days * 86400, 60)
                hours, minutes = divmod(minutes, 60)
                job.job_length = f'{hours:d}:{minutes:02d}:{seconds:02d}'
            else:
                job.job_length = "0:00:00"
            db.session.commit()
