"""
routes/admin.py — Admin blueprint for Waste Wise Bengaluru.
"""

from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, abort,
)
from flask_login import login_required, current_user

import db
import services.report_service as report_service

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

VALID_STATUSES = ['Reported', 'Assigned', 'In Progress', 'Collected', 'Resolved', 'Closed']

# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    from datetime import datetime, timedelta
    raw_stats = db.get_report_stats()
    facilities = db.get_all_facilities()
    open_facilities  = sum(1 for f in facilities if f['status'] == 'OPEN')
    closed_facilities = sum(1 for f in facilities if f['status'] == 'CLOSED')
    agent_logs = db.get_agent_logs(limit=5)
    recent_reports = db.get_all_reports(limit=10)

    # Enrich reports with username
    all_users = {u['id']: u['username'] for u in db.get_all_users()}
    for r in recent_reports:
        r['citizen_username'] = all_users.get(r.get('user_id'), '—')

    # Build stats dict the template expects
    by_status = raw_stats.get('by_status', {})
    stats = {
        'total':              raw_stats.get('total', 0),
        'pending_verification': by_status.get('Reported', 0),
        'assigned':           by_status.get('Assigned', 0),
        'scheduled':          by_status.get('Collection Scheduled', 0),
        'resolved_today':     by_status.get('Resolved', 0),
        'active_facilities':  open_facilities,
    }

    # Category chart — list of {name, count, color}
    category_colors = {
        'Organic/Wet':    '#22c55e', 'Dry/Recyclable': '#3b82f6',
        'E-Waste':        '#f59e0b', 'Construction':   '#a16207',
        'Hazardous':      '#ef4444', 'Mixed':          '#6b7280',
    }
    category_chart = [
        {'name': k, 'count': v, 'color': category_colors.get(k, '#6b7280')}
        for k, v in raw_stats.get('by_category', {}).items()
    ]

    # Status chart — list of {status, count, color}
    status_colors = {
        'Reported': '#6b7280', 'Assigned': '#3b82f6',
        'In Progress': '#f59e0b', 'Collected': '#8b5cf6',
        'Resolved': '#22c55e', 'Closed': '#1f2937',
    }
    status_chart = [
        {'status': k, 'count': v, 'color': status_colors.get(k, '#6b7280')}
        for k, v in by_status.items()
    ]

    # Weekly chart — 7 day breakdown
    conn = db.get_connection()
    weekly_chart = []
    try:
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            cnt = conn.execute(
                "SELECT COUNT(*) FROM waste_reports WHERE DATE(created_at) = ?", (day,)
            ).fetchone()[0]
            weekly_chart.append({'day': day[5:], 'count': cnt})  # MM-DD label
    finally:
        conn.close()

    return render_template(
        'admin/dashboard.html',
        stats=stats,
        facilities=facilities,
        open_facilities=open_facilities,
        closed_facilities=closed_facilities,
        agent_logs=agent_logs,
        recent_reports=recent_reports,
        category_chart=category_chart,
        status_chart=status_chart,
        weekly_chart=weekly_chart,
    )


# ---------------------------------------------------------------------------
# All Reports
# ---------------------------------------------------------------------------

@admin_bp.route('/reports')
@login_required
@admin_required
def all_reports():
    reports = db.get_all_reports(limit=200)

    status_filter   = request.args.get('status', '').strip()
    category_filter = request.args.get('category', '').strip()
    area_filter     = request.args.get('area', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    search_query    = request.args.get('q', '').strip().lower()

    if status_filter:
        reports = [r for r in reports if r['status'] == status_filter]
    if category_filter:
        reports = [r for r in reports if r['waste_category'] == category_filter]
    if area_filter:
        reports = [r for r in reports if r.get('location_area', '') == area_filter]
    if priority_filter:
        reports = [r for r in reports if r.get('priority', '') == priority_filter]
    if search_query:
        reports = [
            r for r in reports
            if search_query in (r.get('report_id', '') or '').lower()
            or search_query in (r.get('description', '') or '').lower()
            or search_query in (r.get('location_area', '') or '').lower()
        ]

    return render_template(
        'admin/all_reports.html',
        reports=reports,
        status_filter=status_filter,
        category_filter=category_filter,
        area_filter=area_filter,
        priority_filter=priority_filter,
        search_query=search_query,
    )


# ---------------------------------------------------------------------------
# Report Management
# ---------------------------------------------------------------------------

@admin_bp.route('/report/<report_id>')
@login_required
@admin_required
def report_manage(report_id):
    report = db.get_report_by_id(report_id)
    if not report:
        abort(404)
    # Enrich with submitter username
    user_dict = db.get_user_by_id(report['user_id'])
    report['citizen_username'] = user_dict['username'] if user_dict else f"citizen #{report['user_id']}"
    audit_trail = db.get_audit_logs_for_report(report_id)
    return render_template(
        'admin/report_manage.html',
        report=report,
        audit_trail=audit_trail,
        valid_statuses=VALID_STATUSES,
    )


@admin_bp.route('/report/<report_id>/status', methods=['POST'])
@login_required
@admin_required
def update_report_status(report_id):
    report = db.get_report_by_id(report_id)
    if not report:
        abort(404)

    new_status      = request.form.get('new_status', '').strip()
    notes           = request.form.get('notes', '').strip()
    collection_date = request.form.get('collection_date', '').strip()

    if new_status not in VALID_STATUSES:
        flash(f'Invalid status "{new_status}".', 'error')
        return redirect(url_for('admin.report_manage', report_id=report_id))

    report_service.update_status(
        report_id=report_id,
        new_status=new_status,
        admin_user_id=current_user.id,
        notes=notes or '',
    )

    if collection_date:
        conn = db.get_connection()
        try:
            conn.execute(
                "UPDATE waste_reports SET collection_date = ?, updated_at = CURRENT_TIMESTAMP WHERE report_id = ?",
                (collection_date, report_id),
            )
            conn.commit()
        finally:
            conn.close()

    flash(f'Report {report_id} status updated to "{new_status}".', 'success')
    return redirect(url_for('admin.report_manage', report_id=report_id))


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    stats = db.get_report_stats()
    facilities = db.get_all_facilities()
    return render_template('admin/analytics.html', stats=stats, facilities=facilities)


# ---------------------------------------------------------------------------
# Agent Logs
# ---------------------------------------------------------------------------

@admin_bp.route('/agent-logs')
@login_required
@admin_required
def agent_logs():
    logs = db.get_agent_logs(limit=100)
    return render_template('admin/agent_logs.html', logs=logs)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = db.get_all_users()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user_dict = db.get_user_by_id(user_id)
    if not user_dict:
        return jsonify({"success": False, "error": "User not found"}), 404

    new_active = not bool(user_dict.get('is_active', 1))
    db.set_user_active(user_id, new_active)

    db.log_audit(
        user_id=current_user.id,
        username=current_user.username,
        action='toggle_user_active',
        entity_type='user',
        entity_id=str(user_id),
        old_status=str(user_dict.get('is_active', 1)),
        new_status=str(int(new_active)),
    )

    return jsonify({"success": True, "is_active": new_active})


# ---------------------------------------------------------------------------
# Facilities
# ---------------------------------------------------------------------------

@admin_bp.route('/facility/<int:facility_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_facility(facility_id):
    facility = db.get_facility_by_id(facility_id)
    if not facility:
        flash('Facility not found.', 'error')
        return redirect(url_for('admin.dashboard'))

    new_status = 'CLOSED' if facility['status'] == 'OPEN' else 'OPEN'
    db.set_facility_status(facility_id, new_status)

    db.log_audit(
        user_id=current_user.id,
        username=current_user.username,
        action='toggle_facility_status',
        entity_type='facility',
        entity_id=str(facility_id),
        old_status=facility['status'],
        new_status=new_status,
    )

    flash(f'Facility "{facility["name"]}" is now {new_status}.', 'success')
    return redirect(url_for('admin.dashboard'))


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    logs = db.get_audit_logs(limit=200)
    return render_template('admin/audit_logs.html', logs=logs)
