"""
ARM route blueprint for notifications pages
Covers
- arm_nav_notify [GET]
- arm_notification [GET]
- arm_notification_close [GET}
"""

from flask_login import login_required  # noqa: F401
from flask import render_template, Blueprint, redirect, flash, session, jsonify
from datetime import datetime

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
                notifications_for_drawer=notifications_for_drawer)


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
