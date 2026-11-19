"""
services/notification_service.py — High-level notification helpers.
"""

import logging

import db

logger = logging.getLogger(__name__)


def notify_report_submitted(user_id, report_id):
    """Send a confirmation notification to the citizen who submitted the report."""
    try:
        db.create_notification(
            user_id=user_id,
            title="Report Submitted",
            message=f"Your waste report {report_id} has been received and is being reviewed.",
            notif_type='info',
            related_report_id=report_id,
        )
    except Exception as exc:
        logger.warning("notify_report_submitted failed: %s", exc)


def notify_status_change(user_id, report_id, old_status, new_status):
    """Notify a citizen that their report status has changed."""
    _STATUS_MESSAGES = {
        'Verified':              ("Report Verified", "success"),
        'Assigned':              ("Collection Assigned", "info"),
        'Collection Scheduled':  ("Collection Scheduled", "info"),
        'Collected':             ("Waste Collected", "success"),
        'Resolved':              ("Report Resolved", "success"),
    }
    title, notif_type = _STATUS_MESSAGES.get(new_status, ("Report Updated", "info"))
    message = (
        f"Your waste report {report_id} status has been updated "
        f"from '{old_status}' to '{new_status}'."
    )
    try:
        db.create_notification(
            user_id=user_id,
            title=title,
            message=message,
            notif_type=notif_type,
            related_report_id=report_id,
        )
    except Exception as exc:
        logger.warning("notify_status_change failed: %s", exc)


def notify_admin_new_report(report_id, waste_category, area):
    """Send a notification to all admin users about a newly submitted report."""
    try:
        admins = [u for u in db.get_all_users() if u.get('role') == 'admin' and u.get('is_active')]
        for admin in admins:
            db.create_notification(
                user_id=admin['id'],
                title="New Waste Report",
                message=(
                    f"A new {waste_category} waste report ({report_id}) "
                    f"has been submitted in {area}."
                ),
                notif_type='info',
                related_report_id=report_id,
            )
    except Exception as exc:
        logger.warning("notify_admin_new_report failed: %s", exc)
