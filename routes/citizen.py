"""
routes/citizen.py — Citizen-facing blueprint for Waste Wise Bengaluru.
"""

import os

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, abort, current_app,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

import db
import services.report_service as report_service

citizen_bp = Blueprint('citizen', __name__, url_prefix='/citizen')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

WASTE_CATEGORIES = [
    'Organic/Wet',
    'Dry/Recyclable',
    'E-Waste',
    'Construction',
    'Hazardous',
    'Mixed',
]


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _redirect_admins():
    """Return a redirect response if the current user is an admin, else None."""
    if current_user.is_admin():
        flash('Admin users should use the admin panel.', 'info')
        return redirect(url_for('admin_bp.dashboard'))
    return None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@citizen_bp.route('/dashboard')
@login_required
def dashboard():
    redir = _redirect_admins()
    if redir:
        return redir

    reports = db.get_reports_by_user(current_user.id)
    total = len(reports)
    pending = sum(1 for r in reports if r['status'] not in ('Resolved', 'Closed'))
    resolved = sum(1 for r in reports if r['status'] in ('Resolved', 'Closed'))
    stats = {'total': total, 'pending': pending, 'resolved': resolved}

    notifications = db.get_notifications_for_user(current_user.id, unread_only=False)[:5]
    unread_count = db.get_unread_count(current_user.id)

    return render_template(
        'citizen/dashboard.html',
        stats=stats,
        recent_reports=reports[:5],
        notifications=notifications,
        unread_count=unread_count,
    )


# ---------------------------------------------------------------------------
# Submit Report
# ---------------------------------------------------------------------------

@citizen_bp.route('/report', methods=['GET'])
@login_required
def report_form():
    redir = _redirect_admins()
    if redir:
        return redir
    categories = WASTE_CATEGORIES
    return render_template('citizen/report_form.html', categories=categories)


@citizen_bp.route('/report', methods=['POST'])
@login_required
def report_submit():
    redir = _redirect_admins()
    if redir:
        return redir

    form_data = {
        'waste_category':    request.form.get('waste_category', 'Mixed'),
        'description':       request.form.get('description', ''),
        'quantity_estimate': request.form.get('quantity_estimate', ''),
        'severity':          request.form.get('severity', 'medium'),
        'priority':          request.form.get('priority', 'normal'),
        'location_area':     request.form.get('location_area', ''),
        'location_details':  request.form.get('location_details', ''),
        'notes':             request.form.get('notes', ''),
    }

    image_file = request.files.get('photo')
    if image_file and image_file.filename:
        if not _allowed_file(image_file.filename):
            flash('Only image files (PNG, JPG, GIF, WebP) are allowed.', 'error')
            return redirect(url_for('citizen.report_form'))

    report = report_service.submit_report(
        user_id=current_user.id,
        form_data=form_data,
        image_file=image_file if (image_file and image_file.filename) else None,
    )

    flash(f'Report submitted successfully! Your report ID is {report["report_id"]}.', 'success')
    return redirect(url_for('citizen.my_reports'))


# ---------------------------------------------------------------------------
# My Reports
# ---------------------------------------------------------------------------

@citizen_bp.route('/reports')
@login_required
def my_reports():
    redir = _redirect_admins()
    if redir:
        return redir

    reports = db.get_reports_by_user(current_user.id)
    status_filter = request.args.get('status', '').strip()
    if status_filter:
        reports = [r for r in reports if r['status'] == status_filter]

    return render_template('citizen/my_reports.html', reports=reports, status_filter=status_filter)


# ---------------------------------------------------------------------------
# Report Detail
# ---------------------------------------------------------------------------

@citizen_bp.route('/report/<report_id>')
@login_required
def report_detail(report_id):
    report = db.get_report_by_id(report_id)
    if not report:
        abort(404)
    if report['user_id'] != current_user.id and not current_user.is_admin():
        abort(403)
    return render_template('citizen/report_detail.html', report=report)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@citizen_bp.route('/notifications')
@login_required
def notifications():
    redir = _redirect_admins()
    if redir:
        return redir

    notifs = db.get_notifications_for_user(current_user.id)
    db.mark_all_notifications_read(current_user.id)
    return render_template('citizen/notifications.html', notifications=notifs)


@citizen_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def notifications_read_all():
    db.mark_all_notifications_read(current_user.id)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Alias: report_waste → report_form (templates use citizen.report_waste)
# ---------------------------------------------------------------------------

@citizen_bp.route('/report-waste', methods=['GET'])
@login_required
def report_waste():
    redir = _redirect_admins()
    if redir:
        return redir
    categories = WASTE_CATEGORIES
    return render_template('citizen/report_form.html', categories=categories)
