"""
ARM route blueprint for log pages
Covers
- logs [GET]
- listlogs [GET]
- logreader [GET]
"""

import os
from pathlib import Path
from flask_login import LoginManager, login_required  # noqa: F401
from flask import render_template, request, Blueprint, send_file, session
from werkzeug.routing import ValidationError

import arm.ui.utils as ui_utils
from arm.ui import app
import arm.config.config as cfg


def _is_progress_log_name(logfile):
    """Accept only a bounded numeric job-id filename for progress logs."""
    if not isinstance(logfile, str) or len(logfile) > 32 or not logfile.endswith(".log"):
        return False
    job_id = logfile[:-4]
    return bool(job_id) and job_id.isascii() and job_id.isdigit()


route_logs = Blueprint('route_logs', __name__,
                       template_folder='templates',
                       static_folder='../static')


@route_logs.route('/logs')
@login_required
def logs():
    """
    This is the main page for viewing a logfile

    this holds the XHR request that sends to other routes for the data
    """
    mode = request.args['mode']
    logfile = request.args['logfile']
    source = "progress" if request.args.get("source") == "progress" else ""
    if source == "progress" and not _is_progress_log_name(logfile):
        raise ValidationError("Invalid MakeMKV progress log")
    session["page_title"] = "Logs"

    return render_template('logview.html', file=logfile, mode=mode, source=source)


@route_logs.route('/listlogs', defaults={'path': ''})
@login_required
def listlogs(path):
    """
    The 'View logs' page - show a list of logfiles in the log folder with creation time and size
    Gives the user links to tail/arm/Full/download
    """
    base_path = cfg.arm_config['LOGPATH']
    full_path = os.path.join(base_path, path)
    session["page_title"] = "Logs"

    # Deal with bad data
    if not os.path.exists(full_path):
        raise ValidationError

    # Get all files in directory
    files = ui_utils.get_info(full_path)
    return render_template('logfiles.html', files=files, date_format=cfg.arm_config['DATE_FORMAT'])


@route_logs.route('/logreader')
@login_required
def logreader():
    """
    The default logreader output function

    This will display or allow downloading the requested logfile
    This is where the XHR requests are sent when viewing /logs?=logfile
    """
    log_path = cfg.arm_config['LOGPATH']
    mode = request.args.get('mode')
    logfile = request.args.get('logfile')
    source = request.args.get('source')
    session["page_title"] = "Logs"

    # Progress logs live in a separate directory. Only numeric job-id filenames
    # are allowed here so a client cannot use this mode to read arbitrary files.
    if source == "progress":
        if not _is_progress_log_name(logfile):
            raise ValidationError("Invalid MakeMKV progress log")
        full_path = os.path.join(log_path, "progress", logfile)
    else:
        full_path = os.path.join(log_path, logfile or "")
    ui_utils.validate_logfile(logfile, mode, Path(full_path))

    # Only ARM logs
    if mode == "armcat":
        generate = ui_utils.generate_arm_cat(full_path)
    # Give everything / Tail
    elif mode == "full":
        generate = ui_utils.generate_full_log(full_path)
    elif mode == "download":
        return send_file(full_path, as_attachment=True)
    else:
        # No mode - error out
        raise ValidationError

    return app.response_class(generate, mimetype='text/plain')
