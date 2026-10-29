"""
ARM route blueprint for settings pages
Covers
- settings [GET]
- save_settings [POST]
- save_ui_settings [POST]
- save_abcde_settings [POST]
- save_apprise_cfg [POST]
- systeminfo [POST]
- systemdrivescan [GET]
- update_arm [POST]
- drive_eject [GET]
- drive_remove [GET]
- testapprise [GET]
- updatesysinfo [GET]
"""
import platform
import importlib
import re
import subprocess
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit
import os

import requests

import sqlalchemy

from flask_login import login_required, \
    current_user, login_user, UserMixin, logout_user  # noqa: F401
from flask import render_template, request, flash, \
    redirect, Blueprint, session, url_for, jsonify

import arm.ui.utils as ui_utils
from arm.ripper.ProcessHandler import arm_subprocess
from arm.ui import app, db
from arm.models.job import Job
from arm.models.system_drives import SystemDrives
from arm.models.system_info import SystemInfo
from arm.models.ui_settings import UISettings
import arm.config.config as cfg
from arm.ui.settings import DriveUtils as drive_utils
from arm.ui.forms import SettingsForm, UiSettingsForm, AbcdeForm, SystemInfoDrives
from arm.ui.settings.ServerUtil import ServerUtil
import arm.ripper.utils as ripper_utils

route_settings = Blueprint('route_settings', __name__,
                           template_folder='templates',
                           static_folder='../static')
REDIRECT_SETTINGS = "route_settings.settings"

# Hardware capability probing launches HandBrake and is therefore cached separately
# from frequently refreshed CPU, memory, and disk readings.
_RESOURCE_HW_SUPPORT_CACHE = {"value": None, "updated_at": 0.0}
_RESOURCE_HW_SUPPORT_CACHE_SECONDS = 300

_TITLE_MODEL_PULL_LOCK = threading.Lock()
_TITLE_MODEL_PULL_STATUS = {
    "status": "idle",
    "message": "Optional model weights have not been downloaded by ARM.",
}


# Human-readable titles for the advanced ripper configuration keys.
_SETTING_LABELS = {
    "ARM_NAME": "ARM Instance Name",
    "ARM_CHILDREN": "Child ARM Servers",
    "PREVENT_99": "Enable Track 99 Workaround",
    "ARM_CHECK_UDF": "Check UDF Video Discs",
    "UMASK": "File Creation Permission Mask",
    "GET_VIDEO_TITLE": "Identify Video Titles",
    "ARM_API_KEY": "ARM API Key",
    "DISABLE_LOGIN": "Disable Login Requirement",
    "FLASK_SECRET_KEY": "Flask Session Signing Key",
    "SKIP_TRANSCODE": "Skip Transcoding",
    "VIDEOTYPE": "Video Type",
    "MINLENGTH": "Minimum Track Length (Seconds)",
    "MAXLENGTH": "Maximum Track Length (Seconds)",
    "MANUAL_WAIT": "Wait for Manual Identification",
    "MANUAL_WAIT_TIME": "Manual Identification Timeout (Seconds)",
    "DATE_FORMAT": "Date and Time Format",
    "ALLOW_DUPLICATES": "Allow Duplicate Discs",
    "MAX_CONCURRENT_TRANSCODES": "Maximum Concurrent Transcodes",
    "MAX_CONCURRENT_MAKEMKVINFO": "Maximum Concurrent MakeMKV Info Jobs",
    "DATA_RIP_PARAMETERS": "Data Disc Rip Parameters",
    "METADATA_PROVIDER": "Metadata Provider",
    "FOLDER_ID_TYPE": "Folder ID Naming Format",
    "GET_AUDIO_TITLE": "Identify Audio CD Titles",
    "RIP_POSTER": "Download Movie Posters",
    "AUTO_EJECT": "Automatically Eject Discs",
    "ABCDE_CONFIG_FILE": "abcde Configuration File",
    "RAW_PATH": "Raw Rip Directory",
    "TRANSCODE_PATH": "Transcode Output Directory",
    "COMPLETED_PATH": "Completed Media Directory",
    "EXTRAS_SUB": "Extras Filename Suffix",
    "INSTALLPATH": "ARM Installation Path",
    "LOGPATH": "Log Directory",
    "LOGLEVEL": "Log Level",
    "LOGLIFE": "Log Retention Period",
    "DBFILE": "Database File Path",
    "WEBSERVER_IP": "Web Server IP Address",
    "WEBSERVER_PORT": "Web Server Port",
    "UI_BASE_URL": "Web UI Base URL",
    "SET_MEDIA_PERMISSIONS": "Set Media Permissions",
    "CHMOD_VALUE": "Media File Permission Mode",
    "SET_MEDIA_OWNER": "Set Media File Owner",
    "CHOWN_USER": "Media Owner Username",
    "CHOWN_GROUP": "Media Owner Group",
    "MAKEMKV_PERMA_KEY": "MakeMKV Registration Key",
    "RIPMETHOD": "Default Rip Method",
    "RIPMETHOD_DVD": "DVD Rip Method",
    "RIPMETHOD_BR": "Blu-ray Rip Method",
    "MKV_ARGS": "MakeMKV Arguments",
    "DELRAWFILES": "Delete Raw Rip Files",
    "HB_PRESET_DVD": "DVD HandBrake Preset",
    "HB_PRESET_BD": "Blu-ray HandBrake Preset",
    "DEST_EXT": "Output File Extension",
    "HANDBRAKE_CLI": "HandBrake CLI Path",
    "HANDBRAKE_LOCAL": "Use Local HandBrake Binary",
    "MAINFEATURE": "Main Feature Track Selection",
    "HB_ARGS_DVD": "DVD HandBrake Arguments",
    "HB_ARGS_BD": "Blu-ray HandBrake Arguments",
    "FFMPEG_CLI": "FFmpeg CLI Path",
    "FFMPEG_LOCAL": "Use Local FFmpeg Binary",
    "FFMPEG_PRE_FILE_ARGS": "FFmpeg Arguments Before Input File",
    "FFMPEG_POST_FILE_ARGS": "FFmpeg Arguments After Input File",
    "USE_FFMPEG": "Use FFmpeg for Transcoding",
    "EMBY_REFRESH": "Refresh Emby Library",
    "EMBY_SERVER": "Emby Server Address",
    "EMBY_PORT": "Emby Server Port",
    "EMBY_CLIENT": "Emby Client Name",
    "EMBY_DEVICE": "Emby Device Name",
    "EMBY_DEVICEID": "Emby Device ID",
    "EMBY_USERNAME": "Emby Username",
    "EMBY_USERID": "Emby User ID",
    "EMBY_PASSWORD": "Emby Password",
    "EMBY_API_KEY": "Emby API Key",
    "NOTIFY_RIP": "Notify After Ripping",
    "NOTIFY_TRANSCODE": "Notify After Transcoding",
    "NOTIFY_JOBID": "Include Job ID in Notifications",
    "PB_KEY": "Pushbullet API Key",
    "IFTTT_KEY": "IFTTT API Key",
    "IFTTT_EVENT": "IFTTT Event Name",
    "PO_USER_KEY": "Pushover User Key",
    "PO_APP_KEY": "Pushover Application Key",
    "BASH_SCRIPT": "Post-Processing Script",
    "EMAIL_NOTIFICATIONS_ENABLED": "Enable Email Notifications",
    "EMAIL_NOTIFY_ERRORS": "Email on Errors",
    "EMAIL_NOTIFY_COMPLETION": "Email on Completion",
    "EMAIL_NOTIFY_OTHER": "Email on Other Events",
    "EMAIL_NOTIFICATION_METHOD": "Email Notification Method",
    "SMTP_HOST": "SMTP Server Hostname",
    "SMTP_PORT": "SMTP Server Port",
    "SMTP_USERNAME": "SMTP Username",
    "SMTP_PASSWORD": "SMTP Password",
    "SMTP_SENDER_EMAIL": "SMTP Sender Email Address",
    "SMTP_RECIPIENTS": "Email Recipients",
    "SMTP_USE_TLS": "Use SMTP STARTTLS",
    "SMTP_USE_SSL": "Use SMTP SSL/TLS",
    "GMAIL_OAUTH_CLIENT_ID": "Gmail OAuth Client ID",
    "GMAIL_OAUTH_CLIENT_SECRET": "Gmail OAuth Client Secret",
    "GMAIL_OAUTH_REFRESH_TOKEN": "Gmail OAuth Refresh Token",
    "GMAIL_SENDER_EMAIL": "Gmail Sender Email Address",
    "GMAIL_RECIPIENTS": "Gmail Recipients",
    "OMDB_API_KEY": "OMDb API Key",
    "TMDB_API_KEY": "TMDB API Key",
    "JSON_URL": "JSON Notification URL",
    "APPRISE": "Apprise Configuration File",
}


def humanize_setting_name(value):
    """Return a readable English label for a configuration key."""
    key = str(value)
    return _SETTING_LABELS.get(key, " ".join(word.capitalize() for word in key.replace("_", " ").split()))


def mask_last(value, n=4):
    """
    Replaces the last `n` characters of a string with asterisks.
    """
    if not isinstance(value, str):
        return value
    return value[:-n] + '*' * n if len(value) > n else '*' * len(value)


def is_read_only(path: os.PathLike) -> bool:
    return not os.access(path, os.W_OK)


route_settings.add_app_template_filter(mask_last, name='mask_last')
route_settings.add_app_template_filter(humanize_setting_name, name='humanize_setting')


@route_settings.route('/settings')
@login_required
def settings():
    """
    Page - settings
    Method - GET
    Overview - allows the user to update the all configs of A.R.M without
    needing to open a text editor
    """

    # stats for info page
    failed_rips = Job.query.filter_by(status="fail").count()
    total_rips = Job.query.filter_by().count()
    movies = Job.query.filter_by(video_type="movie").count()
    series = Job.query.filter_by(video_type="series").count()
    cds = Job.query.filter_by(disctype="music").count()

    # Get the current server time and timezone
    server_timezone = os.environ.get("TZ", "Etc/UTC")
    current_time = datetime.now()
    server_datetime = current_time.strftime(cfg.arm_config['DATE_FORMAT'])
    [arm_version_local, arm_version_remote] = ui_utils.git_check_version()
    local_git_hash = ui_utils.get_git_revision_hash()

    stats = {'server_datetime': server_datetime,
             'server_timezone': server_timezone,
             'python_version': platform.python_version(),
             'arm_version_local': arm_version_local,
             'arm_version_remote': arm_version_remote,
             'git_commit': local_git_hash,
             'movies_ripped': movies,
             'series_ripped': series,
             'cds_ripped': cds,
             'no_failed_jobs': failed_rips,
             'total_rips': total_rips,
             'updated': ui_utils.git_check_updates(local_git_hash),
             'hw_support': check_hw_transcode_support()
             }

    # ARM UI config
    armui_cfg = ui_utils.arm_db_cfg()

    # Get system details from Server Info and Config
    server = SystemInfo.query.filter_by(id="1").first()
    serverutil = ServerUtil()
    arm_path = cfg.arm_config['TRANSCODE_PATH']
    media_path = cfg.arm_config['COMPLETED_PATH']

    # System Drives (CD/DVD/Blueray drives)
    drive_utils.update_job_status()
    drives = drive_utils.get_drives()
    drive_utils.update_tray_status(drives)
    form_drive = SystemInfoDrives(request.form)

    # Load up the comments.json, so we can comment the arm.yaml
    comments = ui_utils.generate_comments()
    form = SettingsForm()

    session["page_title"] = "Settings"

    app.logger.debug(f"stats: {stats}")

    return render_template("settings/settings.html",
                           settings=cfg.arm_config,
                           ui_settings=armui_cfg,
                           stats=stats,
                           apprise_cfg=cfg.apprise_config,
                           form=form,
                           jsoncomments=comments,
                           abcde_cfg=cfg.abcde_config,
                           server=server,
                           serverutil=serverutil,
                           arm_path=arm_path,
                           media_path=media_path,
                           drives=drives,
                           form_drive=form_drive,
                           ripper_read_only=is_read_only(cfg.arm_config_path),
                           apprise_read_only=is_read_only(cfg.apprise_config_path),
                           abcde_read_only=is_read_only(cfg.abcde_config_path))


def check_hw_transcode_support():
    cmd = f"nice {cfg.arm_config['HANDBRAKE_CLI']}"

    app.logger.debug(f"Sending command: {cmd}")
    hw_support_status = {
        "nvidia": False,
        "intel": False,
        "amd": False
    }
    try:
        hand_brake_output = arm_subprocess(f"{cmd}", shell=True, check=True)

        # NVENC
        if re.search(r'nvenc: version ([0-9\\.]+) is available', str(hand_brake_output)):
            app.logger.info("NVENC supported!")
            hw_support_status["nvidia"] = True
        # Intel QuickSync
        if re.search(r'qsv:\sis(.*?)available\son', str(hand_brake_output)):
            app.logger.info("Intel QuickSync supported!")
            hw_support_status["intel"] = True
        # AMD VCN
        if re.search(r'vcn:\sis(.*?)available\son', str(hand_brake_output)):
            app.logger.info("AMD VCN supported!")
            hw_support_status["amd"] = True
        app.logger.info("Handbrake call successful")
        app.logger.debug(hand_brake_output)
    except subprocess.CalledProcessError:
        pass
    return hw_support_status


@route_settings.route('/save_settings', methods=['POST'])
@login_required
def save_settings():  # noqa: C901
    """
    Page - save_settings
    Method - POST
    Overview - Save arm ripper settings from post. Not a user page
    """
    # Load up the comments.json, so we can comment the arm.yaml
    comments = ui_utils.generate_comments()
    success = False
    arm_cfg = {}
    form = SettingsForm()
    if form.validate_on_submit():
        # Build the new arm.yaml with updated values from the user
        arm_cfg = ui_utils.build_arm_cfg(request.form.to_dict(), comments)
        # Save updated arm.yaml
        try:
            with open(cfg.arm_config_path, "w") as settings_file:
                settings_file.write(arm_cfg)
                settings_file.close()
            success = True
            importlib.reload(cfg)
            # Jobs snapshot settings into a per-job Config row; synchronize active
            # jobs so a changed folder-ID policy applies to jobs already running.
            id_type = str(cfg.arm_config.get("FOLDER_ID_TYPE", "none")).strip().lower()
            try:
                active_jobs = Job.query.filter(Job.status.notin_(["success", "fail"])).all()
                for active_job in active_jobs:
                    if active_job.config is not None:
                        active_job.config.FOLDER_ID_TYPE = id_type
                    if (id_type == "tmdb" and not active_job.tmdb_id and active_job.imdb_id
                            and cfg.arm_config.get("TMDB_API_KEY")):
                        try:
                            details = ui_utils.tmdb_find(active_job.imdb_id)
                            if details:
                                active_job.tmdb_id = details.get("tmdbID") or (
                                    str(details["results"][0].get("id")) if details.get("results") else None
                                )
                        except Exception as error:
                            app.logger.warning("Could not resolve TMDB ID for job %s: %s",
                                               active_job.job_id, error)
                    elif (id_type == "imdb" and not active_job.imdb_id and active_job.tmdb_id
                          and cfg.arm_config.get("TMDB_API_KEY")):
                        try:
                            details = ui_utils.tmdb_details(active_job.tmdb_id, active_job.video_type)
                            if details and details.get("imdbID"):
                                active_job.imdb_id = active_job.imdb_id_auto = details["imdbID"]
                        except Exception as error:
                            app.logger.warning("Could not resolve IMDb ID for job %s: %s",
                                               active_job.job_id, error)
                db.session.commit()
            except Exception as error:
                db.session.rollback()
                app.logger.error("Could not sync naming policy to active jobs: %s", error)
            # Set the ARM Log level to the config
            app.logger.info(f"Setting log level to: {cfg.arm_config['LOGLEVEL']}")
            app.logger.setLevel(cfg.arm_config['LOGLEVEL'])
        except OSError as e:
            # arm.yaml is read-only
            app.logger.error(f"{cfg.arm_config_path} is read-only", exc_info=e)

    return {'success': success, 'settings': cfg.arm_config, 'form': 'arm ripper settings'}


@route_settings.route('/save_ui_settings', methods=['POST'])
@login_required
def save_ui_settings():
    """
    Page - save_ui_settings
    Method - POST
    Overview - Save 'UI Settings' page settings to database. Not a user page
    Notes - This function needs to trigger a restart of flask for
        debugging to update the values
    """
    form = UiSettingsForm()
    success = False
    arm_ui_cfg = UISettings.query.get(1)
    if form.validate_on_submit():
        use_icons = (str(form.use_icons.data).strip().lower() == "true")
        save_remote_images = (str(form.save_remote_images.data).strip().lower() == "true")
        arm_ui_cfg.index_refresh = format(form.index_refresh.data)
        arm_ui_cfg.use_icons = use_icons
        arm_ui_cfg.save_remote_images = save_remote_images
        arm_ui_cfg.bootstrap_skin = format(form.bootstrap_skin.data)
        arm_ui_cfg.language = format(form.language.data)
        arm_ui_cfg.database_limit = format(form.database_limit.data)
        arm_ui_cfg.notify_refresh = format(form.notify_refresh.data)
        arm_ui_cfg.show_job_ripper = bool(form.show_job_ripper.data)
        arm_ui_cfg.show_job_rip_method = bool(form.show_job_rip_method.data)
        arm_ui_cfg.show_job_main_feature = bool(form.show_job_main_feature.data)
        arm_ui_cfg.show_job_min_length = bool(form.show_job_min_length.data)
        arm_ui_cfg.show_job_max_length = bool(form.show_job_max_length.data)
        arm_ui_cfg.device_display_mode = form.device_display_mode.data or "coded"
        arm_ui_cfg.start_date_format = form.start_date_format.data or "MM/DD/YYYY"
        arm_ui_cfg.start_time_format = form.start_time_format.data or "12h"
        arm_ui_cfg.smart_title_matching_enabled = bool(form.smart_title_matching_enabled.data)
        arm_ui_cfg.smart_title_matching_url = (
            str(form.smart_title_matching_url.data or "").strip() or "http://ollama:11434"
        )
        arm_ui_cfg.smart_title_matching_model = (
            str(form.smart_title_matching_model.data or "").strip() or "qwen2.5:3b"
        )
        db.session.commit()
        success = True
        # Refresh the global used by the active-rip template so format changes apply
        # immediately without requiring a Flask restart.
        app.jinja_env.globals.update(armui_cfg=UISettings.query.get(1))
    # Masking the jinja update, otherwise an error is thrown
    # sqlalchemy.orm.exc.DetachedInstanceError: Instance <UISettings at 0x7f294c109fd0>
    # app.jinja_env.globals.update(armui_cfg=arm_ui_cfg)
    return {'success': success, 'settings': str(arm_ui_cfg), 'form': 'arm ui settings'}




def _pull_smart_title_model(endpoint, model_name):
    """Download model weights from the configured Ollama service in a background thread."""
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Ollama URL must be an absolute HTTP or HTTPS URL.")
        api_root = endpoint.rstrip("/")
        pull_url = api_root + "/pull" if api_root.endswith("/api") else api_root + "/api/pull"
        response = requests.post(
            pull_url,
            json={"name": model_name, "stream": False},
            timeout=(5, 1800),
        )
        response.raise_for_status()
        result = response.json()
        if result.get("error"):
            raise RuntimeError(str(result["error"]))
        with _TITLE_MODEL_PULL_LOCK:
            _TITLE_MODEL_PULL_STATUS.update(
                status="success",
                message="Model weights downloaded successfully.",
            )
        app.logger.info("Optional smart title model download completed.")
    except Exception as error:
        with _TITLE_MODEL_PULL_LOCK:
            _TITLE_MODEL_PULL_STATUS.update(
                status="error",
                message="Model download failed: " + str(error)[:400],
            )
        app.logger.exception("Optional smart title model download failed.")


@route_settings.route('/install_smart_title_model', methods=['POST'])
@login_required
def install_smart_title_model():
    """Request an Ollama model pull; Ollama itself must already be installed separately."""
    settings_row = UISettings.query.get(1)
    if settings_row is None:
        return jsonify({"success": False, "message": "UI settings are not initialized."}), 400
    endpoint = str(
        request.form.get("smart_title_matching_url") or settings_row.smart_title_matching_url or ""
    ).strip()
    model_name = str(
        request.form.get("smart_title_matching_model") or settings_row.smart_title_matching_model or ""
    ).strip()
    if not endpoint or not model_name or len(model_name) > 128:
        return jsonify({"success": False, "message": "Enter a valid Ollama URL and model name."}), 400
    parsed = urlsplit(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return jsonify({"success": False, "message": "Ollama URL must be an absolute HTTP or HTTPS URL."}), 400
    with _TITLE_MODEL_PULL_LOCK:
        if _TITLE_MODEL_PULL_STATUS.get("status") == "running":
            return jsonify({"success": True, **_TITLE_MODEL_PULL_STATUS})
        _TITLE_MODEL_PULL_STATUS.update(status="running", message="Connecting to Ollama and downloading model weights.")
    worker = threading.Thread(
        target=_pull_smart_title_model,
        args=(endpoint, model_name),
        name="arm-smart-title-model-pull",
        daemon=True,
    )
    worker.start()
    return jsonify({"success": True, "status": "running", "message": "Model download started."})


@route_settings.route('/smart_title_model_status')
@login_required
def smart_title_model_status():
    """Return the status of the optional Ollama model download."""
    with _TITLE_MODEL_PULL_LOCK:
        return jsonify(dict(_TITLE_MODEL_PULL_STATUS))


@route_settings.route('/save_abcde_settings', methods=['POST'])
@login_required
def save_abcde():
    """
    Page - save_abcde_settings
    Method - POST
    Overview - Save 'abcde Config' page settings to the database. Not a user page
    """
    success = False
    abcde_cfg_str = ""
    form = AbcdeForm()
    if form.validate():
        app.logger.debug(f"routes.save_abcde: Saving new abcde.conf: {cfg.abcde_config_path}")
        abcde_cfg_str = str(form.abcdeConfig.data).strip()
        # Windows machines can put \r\n instead of \n newlines, which corrupts the config file
        clean_abcde_str = '\n'.join(abcde_cfg_str.splitlines())
        # Save updated abcde.conf
        try:
            with open(cfg.abcde_config_path, "w") as abcde_file:
                abcde_file.write(clean_abcde_str)
                abcde_file.close()
            success = True
            # Update the abcde config
            cfg.abcde_config = clean_abcde_str
        except OSError as e:
            app.logger.error(f"{cfg.abcde_config_path} is read-only", exc_info=e)

    # If we get to here, there was no post-data
    return {'success': success,
            'settings': clean_abcde_str,
            'form': 'abcde config'}


@route_settings.route('/save_apprise_cfg', methods=['POST'])
@login_required
def save_apprise_cfg():
    """
    Page - save_apprise_cfg
    Method - POST
    Overview - Save 'Apprise Config' page settings to database. Not a user page
    """
    success = False
    # Since we can't be sure of any values, we can't validate it
    if request.method == 'POST':
        # Save updated apprise.yaml
        # Build the new arm.yaml with updated values from the user
        apprise_cfg = ui_utils.build_apprise_cfg(request.form.to_dict())
        try:
            with open(cfg.apprise_config_path, "w") as settings_file:
                settings_file.write(apprise_cfg)
                settings_file.close()
            success = True
            importlib.reload(cfg)
        except OSError as e:
            app.logger.error(f"{cfg.apprise_config_path} is read-only", exc_info=e)
    # If we get to here there was no post data
    return {'success': success, 'settings': cfg.apprise_config, 'form': 'Apprise config'}


@route_settings.route('/systeminfo', methods=['POST'])
@login_required
def server_info():
    """
    Page - systeminfo
    Method - POST
    Overview - Save 'System Info' page settings to database. Not a user page
    """
    # System Drives (CD/DVD/Blueray drives)
    form_drive = SystemInfoDrives(request.form)
    if request.method == 'POST' and form_drive.validate():
        # Return for POST
        app.logger.debug(
            f"Drive id: {str(form_drive.id.data)} " +
            f"Updated name: {str(form_drive.name.data)} " +
            f"Updated description: [{str(form_drive.description.data)}] " +
            f"Updated mode: [{str(form_drive.drive_mode.data)}]")
        drive = SystemDrives.query.filter_by(drive_id=form_drive.id.data).first()
        drive.description = str(form_drive.description.data).strip()
        drive.name = str(form_drive.name.data).strip()
        drive.drive_mode = str(form_drive.drive_mode.data).strip()
        db.session.commit()
        flash(f"Updated Drive {drive.name} details", "success")
        # Return to the systeminfo page (refresh page)
        return redirect(url_for(REDIRECT_SETTINGS))
    else:
        flash("Error: Unable to update drive details", "error")
        # Return for GET
        return redirect(url_for(REDIRECT_SETTINGS))


@route_settings.route('/systemdrivescan')
def system_drive_scan():
    """
    Page - systemdrivescan
    Method - GET
    Overview - Scan for the system drives and update the database.
    """
    # Update to scan for changes to the ripper system
    new_count = drive_utils.drives_update()
    flash(f"ARM found {new_count} new drives", "success")
    return redirect(url_for(REDIRECT_SETTINGS))


@route_settings.route('/drive/eject/<eject_id>')
@login_required
def drive_eject(eject_id):
    """
    Server System - change state of CD/DVD/BluRay drive - toggle eject status
    """
    try:
        drive = SystemDrives.query.filter_by(drive_id=eject_id).one()
    except sqlalchemy.exc.NoResultFound as e:
        app.logger.error(f"Drive eject encountered an error: {e}")
        flash(f"Cannot find drive {eject_id} in database.", "error")
        return redirect(url_for(REDIRECT_SETTINGS))
    # block for running jobs
    if drive.job_id_current:
        drive.tray_status()  # update tray status
        if not drive.open:  # allow closing
            flash(f"Job [{drive.job_id_current}] in progress. Cannot eject {eject_id}.", "error")
            return redirect(url_for(REDIRECT_SETTINGS))
    # toggle open/close (with non-critical error)
    if (error := drive.eject(method="toggle")) is not None:
        flash(error, "error")
    return redirect(url_for(REDIRECT_SETTINGS))


@route_settings.route('/drive/remove/<remove_id>')
@login_required
def drive_remove(remove_id):
    """
    Server System - remove a drive from the ARM UI
    """
    try:
        app.logger.debug(f"Removing drive {remove_id}")
        drive = SystemDrives.query.filter_by(drive_id=remove_id).first()
        dev_path = drive.mount
        SystemDrives.query.filter_by(drive_id=remove_id).delete()
        db.session.commit()
        flash(f"Removed drive [{dev_path}] from ARM", "success")
    except Exception as e:
        app.logger.error(f"Drive removal encountered an error: {e}")
        flash("Drive unable to be removed, check logs for error", "error")
    return redirect(url_for(REDIRECT_SETTINGS))


@route_settings.route('/drive/manual/<manual_id>')
@login_required
def drive_manual(manual_id):
    """
    Manually start a job on ARM
    """

    drive = SystemDrives.query.filter_by(drive_id=manual_id).first()
    dev_path = drive.mount.lstrip('/dev/')

    cmd = os.path.join(
        cfg.arm_config["INSTALLPATH"],
        f"scripts/docker/docker_arm_wrapper.sh {dev_path}",
    )
    app.logger.debug(f"Running command[{cmd}]")

    # Manually start ARM if the udev rules are not working for some reason
    try:
        manual_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = manual_process.communicate()

        if manual_process.returncode != 0:
            raise subprocess.CalledProcessError(manual_process.returncode, cmd, output=stdout, stderr=stderr)

        message = f"Manually starting a job on Drive: '{drive.name}'"
        status = "success"
        app.logger.debug(stdout)

    except subprocess.CalledProcessError as e:
        message = f"Failed to start a job on Drive: '{drive.name}' See logs for info"
        status = "danger"
        app.logger.error(message)
        app.logger.error(f"error: {e}")
        app.logger.error(f"stdout: {e.output}")
        app.logger.error(f"stderr: {e.stderr}")

    flash(message, status)
    return redirect('/settings')


@route_settings.route('/testapprise')
def testapprise():
    """
    Page - testapprise
    Method - GET
    Overview - Send a test notification to Apprise.
    """
    # Send a sample notification
    message = "This is a notification by the ARM-Notification Test!"
    if cfg.arm_config["UI_BASE_URL"] and cfg.arm_config["WEBSERVER_PORT"]:
        message = message + f" Server URL: http://{cfg.arm_config['UI_BASE_URL']}:{cfg.arm_config['WEBSERVER_PORT']}"
    ripper_utils.notify(None, "ARM notification", message)
    flash("Test notification sent ", "success")
    return redirect(url_for(REDIRECT_SETTINGS))


@route_settings.route('/updatesysinfo')
def update_sysinfo():
    """
    Update system information
    """
    # Get current system information from database
    current_system = SystemInfo.query.first()
    # Query system for new information
    new_system = SystemInfo()

    app.logger.debug("****** System Information ******")
    if current_system is not None:
        app.logger.debug(f"Name old [{current_system.name}] new [{new_system.name}]")
        app.logger.debug(f"Name old [{current_system.cpu}] new [{new_system.cpu}]")
        app.logger.debug(f"Name old [{current_system.mem_total}] new [{new_system.mem_total}]")
        current_system.name = new_system.name
        current_system.cpu = new_system.cpu
        current_system.mem_total = new_system.mem_total
        db.session.add(current_system)
    else:
        app.logger.debug(f"Name old [No Info] new [{new_system.name}]")
        app.logger.debug(f"Name old [No Info] new [{new_system.cpu}]")
        app.logger.debug(f"Name old [No Info] new [{new_system.mem_total}]")
        db.session.add(new_system)

    app.logger.debug("****** End System Information ******")
    app.logger.info(f"Updated CPU Details with new info - {new_system.name} - {new_system.cpu} - "
                    f"{new_system.mem_total}")

    db.session.commit()

    return redirect(url_for(REDIRECT_SETTINGS))


@route_settings.route('/resource_metrics')
@login_required
def resource_metrics():  # noqa: C901
    """Return current system, storage and transcoding-capability data for the resource drawer."""
    import psutil

    def read_limit(paths):
        for path in paths:
            try:
                with open(path, "r", encoding="ascii") as handle:
                    value = handle.read().strip()
                if value and value != "max":
                    number = int(value)
                    if number > 0:
                        return number
            except (OSError, ValueError):
                continue
        return None

    def disk_metrics(path):
        try:
            usage = psutil.disk_usage(path)
            return {
                "available": True,
                "percent": round(usage.percent, 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "path": path,
            }
        except (OSError, TypeError, ValueError):
            return {"available": False, "percent": None, "free_gb": None, "path": path}

    def cpu_temperature():
        try:
            temperatures = psutil.sensors_temperatures()
        except (AttributeError, NotImplementedError, OSError, RuntimeError):
            return None
        for group_name in ("coretemp", "cpu_thermal", "k10temp"):
            for sensor in temperatures.get(group_name, ()):
                current = getattr(sensor, "current", None)
                if current is not None:
                    return round(float(current), 1)
        for group_name, sensors in temperatures.items():
            if "cpu" not in group_name.lower():
                continue
            for sensor in sensors:
                current = getattr(sensor, "current", None)
                if current is not None:
                    return round(float(current), 1)
        return None

    memory = psutil.virtual_memory()
    # Prefer cgroup limits when present; psutil alone may report host memory in containers.
    limit = read_limit(("/sys/fs/cgroup/memory.max",
                        "/sys/fs/cgroup/memory/memory.limit_in_bytes"))
    usage = read_limit(("/sys/fs/cgroup/memory.current",
                        "/sys/fs/cgroup/memory/memory.usage_in_bytes"))
    if limit is not None and limit < (1 << 60):
        total_bytes = limit
        used_bytes = usage if usage is not None else max(0, total_bytes - memory.available)
        available_bytes = max(0, total_bytes - used_bytes)
        memory_percent = round(min(100, used_bytes * 100 / total_bytes), 1)
        scope = "container memory limit detected"
    else:
        total_bytes = memory.total
        used_bytes = memory.used
        available_bytes = memory.available
        memory_percent = round(memory.percent, 1)
        scope = "runtime memory view; container limit not detected"

    server = SystemInfo.query.filter_by(id="1").first()
    now = time.monotonic()
    if (_RESOURCE_HW_SUPPORT_CACHE["value"] is None
            or now - _RESOURCE_HW_SUPPORT_CACHE["updated_at"] >= _RESOURCE_HW_SUPPORT_CACHE_SECONDS):
        try:
            _RESOURCE_HW_SUPPORT_CACHE["value"] = check_hw_transcode_support()
        except Exception:
            app.logger.exception("Unable to refresh hardware transcoding support")
            if _RESOURCE_HW_SUPPORT_CACHE["value"] is None:
                _RESOURCE_HW_SUPPORT_CACHE["value"] = {
                    "intel": False, "nvidia": False, "amd": False
                }
        _RESOURCE_HW_SUPPORT_CACHE["updated_at"] = now

    return jsonify({
        "system_name": getattr(server, "name", None) or cfg.arm_config.get("ARM_NAME") or "ARM Server",
        "system_description": (
            getattr(server, "description", None)
            or "Automatic Ripping Machine main server"
        ),
        "cpu_model": getattr(server, "cpu", None) or platform.processor() or "Unavailable",
        "cpu_temp_c": cpu_temperature(),
        "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
        "memory_used_gb": round(used_bytes / (1024 ** 3), 2),
        "memory_available_gb": round(available_bytes / (1024 ** 3), 2),
        "memory_percent": memory_percent,
        "memory_total_gb": round(total_bytes / (1024 ** 3), 2),
        "storage_transcode": disk_metrics(cfg.arm_config.get("TRANSCODE_PATH", "")),
        "storage_completed": disk_metrics(cfg.arm_config.get("COMPLETED_PATH", "")),
        "hw_support": _RESOURCE_HW_SUPPORT_CACHE["value"],
        "scope": scope,
    })
