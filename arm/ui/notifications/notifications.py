"""
ARM route blueprint for notifications pages
Covers
- arm_nav_notify [GET]
- arm_notification [GET]
- arm_notification_close [GET}
"""

from flask_login import login_required  # noqa: F401
from flask import render_template, Blueprint, redirect, flash, session, jsonify, request
from datetime import datetime
import importlib
import os

import arm.config.config as cfg

import arm.ui.utils as ui_utils
from arm.ui import app, db
from arm.models.notifications import Notifications

route_notifications = Blueprint('route_notifications', __name__,
                                template_folder='templates',
                                static_folder='../static')


@app.context_processor
def arm_nav_notify():
    """
    inject the unread notification count to all pages for the navbar count
    """
    try:
        unread = Notifications.query.filter_by(cleared=False)
        notify_count = unread.count()
        notifications_for_drawer = unread.order_by(Notifications.id.desc()).limit(50).all()
        app.logger.debug("Unread notifications: %s", notify_count)
    except Exception:
        notify_count = 0
        notifications_for_drawer = []
        app.logger.debug("Unable to load notifications for drawer", exc_info=True)

    return dict(notify_count=notify_count,
                notifications_for_drawer=notifications_for_drawer,
                email_notification_preferences={key: cfg.arm_config.get(key, True) for key in (
                    "EMAIL_NOTIFICATIONS_ENABLED", "EMAIL_NOTIFY_ERRORS",
                    "EMAIL_NOTIFY_COMPLETION", "EMAIL_NOTIFY_OTHER"
                )})


@route_notifications.route('/notificationview')
@login_required
def arm_notification():
    """
    function to display all current notifications
    """
    notifications_new = Notifications.query.filter_by(cleared='0').order_by(Notifications.id.desc()).all()

    if len(notifications_new) != 0:
        if len(notifications_new) > 100:
            flash(f'Please note clearing {len(notifications_new)} Notifications will take some time', 'warning')

        # get the current time for each notification and then save back into notification
        for notification in notifications_new:
            notification.diff_time = datetime.now().replace(microsecond=0) - notification.trigger_time
    else:
        notifications_new = None

    session["page_title"] = "Notifications"

    return render_template('notificationview.html',
                           notifications_new=notifications_new)


@route_notifications.route('/notificationclose')
@login_required
def arm_notification_close():
    """
    function to close all open notifications
    """
    notifications = Notifications.query.filter_by(cleared='0').all()

    if len(notifications) != 0:
        # get the current time for each notification and then save back into notification
        for notification in notifications:
            args = {
                'cleared': True,
                'cleared_time': datetime.now()
            }
            ui_utils.database_updater(args, notification)

        flash(f'Cleared {len(notifications)} Notifications', 'success')
    else:
        flash('No notifications to clear', 'error')

    return redirect("/notificationview")


@route_notifications.route('/notificationclear', methods=['POST'])
@login_required
def arm_notification_clear():
    """Clear unread notifications from the global notification drawer."""
    try:
        notifications = Notifications.query.filter_by(cleared=False).all()
        cleared_at = datetime.now()
        for notification in notifications:
            notification.cleared = True
            notification.cleared_time = cleared_at
        db.session.commit()
        return jsonify({"success": True, "cleared_count": len(notifications)})
    except Exception:
        db.session.rollback()
        app.logger.exception("Unable to clear notifications from drawer")
        return jsonify({"success": False, "message": "Unable to clear notifications"}), 500


@route_notifications.route('/notificationpreferences', methods=['POST'])
@login_required
def arm_notification_preferences():
    """Persist email notification preferences changed in the notification drawer."""
    allowed = {
        "EMAIL_NOTIFICATIONS_ENABLED",
        "EMAIL_NOTIFY_ERRORS",
        "EMAIL_NOTIFY_COMPLETION",
        "EMAIL_NOTIFY_OTHER",
    }
    payload = request.get_json(silent=True) or {}
    key = payload.get("key")
    if key not in allowed or not isinstance(payload.get("enabled"), bool):
        return jsonify({"success": False, "message": "Invalid notification preference"}), 400
    if not os.access(cfg.arm_config_path, os.W_OK):
        return jsonify({"success": False, "message": "ARM configuration is read-only"}), 403

    updated_config = {name: str(value) for name, value in cfg.arm_config.items()}
    updated_config[key] = "true" if payload["enabled"] else "false"
    try:
        comments = ui_utils.generate_comments()
        rendered_config = ui_utils.build_arm_cfg(updated_config, comments)
        with open(cfg.arm_config_path, "w", encoding="utf-8") as settings_file:
            settings_file.write(rendered_config)
        importlib.reload(cfg)
        return jsonify({"success": True, "key": key, "enabled": cfg.arm_config.get(key, True)})
    except OSError:
        app.logger.exception("Unable to save notification preferences")
        return jsonify({"success": False, "message": "Unable to save notification preferences"}), 500
