"""
services/report_service.py — Business logic for citizen waste reports.
"""

import os
import logging

import db
from services.notification_service import (
    notify_report_submitted,
    notify_status_change,
    notify_admin_new_report,
)

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_image(image_file, report_id):
    """Save an uploaded image file and return its relative path, or None on failure."""
    if image_file is None or image_file.filename == '':
        return None
    if not _allowed_file(image_file.filename):
        return None
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        ext = image_file.filename.rsplit('.', 1)[1].lower()
        filename = f"{report_id}.{ext}"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(save_path)
        return f"uploads/{filename}"
    except Exception as exc:
        logger.warning("Could not save image for %s: %s", report_id, exc)
        return None


def submit_report(user_id, form_data, image_file=None):
    """
    Create a new waste report.

    Parameters
    ----------
    user_id   : int
    form_data : dict with keys:
                  waste_category, description, quantity_estimate,
                  severity, priority, location_area, location_details
    image_file: werkzeug FileStorage or None

    Returns
    -------
    dict — the saved report record
    """
    # Insert report without image first to get the report_id
    report = db.insert_waste_report(
        user_id=user_id,
        waste_category=form_data.get('waste_category', 'Mixed'),
        description=form_data.get('description', ''),
        quantity_estimate=form_data.get('quantity_estimate', ''),
        severity=form_data.get('severity', 'medium'),
        priority=form_data.get('priority', 'normal'),
        location_area=form_data.get('location_area', ''),
        location_details=form_data.get('location_details', ''),
        image_path=None,
    )

    # Save image now that we have the report_id
    if image_file:
        image_path = _save_image(image_file, report['report_id'])
        if image_path:
            db.update_report_status(report['report_id'], report['status'])  # no-op status update
            # patch image_path directly
            conn = db.get_connection()
            try:
                conn.execute(
                    "UPDATE waste_reports SET image_path = ? WHERE report_id = ?",
                    (image_path, report['report_id']),
                )
                conn.commit()
                report['image_path'] = image_path
            finally:
                conn.close()

    # Notify the submitting user
    notify_report_submitted(user_id, report['report_id'])

    # Notify all admins
    notify_admin_new_report(
        report['report_id'],
        report['waste_category'],
        report['location_area'],
    )

    # Trigger AI analysis (synchronous for MVP)
    try:
        trigger_ai_analysis(report['report_id'])
        # Reload report to include AI fields
        updated = db.get_report_by_id(report['report_id'])
        if updated:
            report = updated
    except Exception as exc:
        logger.warning("AI analysis failed for %s: %s", report['report_id'], exc)

    return report


def trigger_ai_analysis(report_id):
    """
    Run AI analysis on a waste report and persist the result.

    Calls the enhanced load_intake agent. Falls back gracefully on error.
    """
    report = db.get_report_by_id(report_id)
    if not report:
        raise ValueError(f"Report {report_id} not found")

    from agents.load_intake import analyze_waste_report

    input_data = {
        'waste_category': report.get('waste_category'),
        'description': report.get('description'),
        'quantity_estimate': report.get('quantity_estimate'),
        'location_area': report.get('location_area'),
        'severity': report.get('severity'),
    }

    result = analyze_waste_report(input_data)

    db.update_report_ai_analysis(
        report_id=report_id,
        ai_category=result.get('ai_category'),
        ai_severity=result.get('ai_severity'),
        ai_priority=result.get('ai_priority'),
        ai_action=result.get('ai_recommended_action'),
    )

    db.log_agent_action(
        agent_name='load_intake',
        action='analyze_waste_report',
        input_data=input_data,
        output_data=result,
        report_id=report_id,
        status='success',
    )

    return result


def update_status(report_id, new_status, admin_user_id, notes=''):
    """
    Update a report's status, notify the report owner, and log the audit event.

    Parameters
    ----------
    report_id      : str  e.g. "WR-2024-00001"
    new_status     : str
    admin_user_id  : int
    notes          : str  optional admin note
    """
    report = db.get_report_by_id(report_id)
    if not report:
        raise ValueError(f"Report {report_id} not found")

    old_status = report['status']
    db.update_report_status(report_id, new_status, updated_by_user_id=admin_user_id, notes=notes or None)

    # Notify the report owner
    notify_status_change(report['user_id'], report_id, old_status, new_status)

    # Audit trail
    admin = db.get_user_by_id(admin_user_id)
    db.log_audit(
        user_id=admin_user_id,
        username=admin['username'] if admin else str(admin_user_id),
        action='update_report_status',
        entity_type='report',
        entity_id=report_id,
        old_status=old_status,
        new_status=new_status,
        details=notes,
    )

    return db.get_report_by_id(report_id)
