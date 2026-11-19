"""
db.py — SQLite connection and query helpers for Waste Wise Bengaluru.
Uses SQLite (zero-install) for the MVP demo.
Credentials/config are loaded from .env via python-dotenv.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "wastewise.db"))


def get_connection():
    """Return a new SQLite connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# Schema initialisation (auto-run on first import)
# ---------------------------------------------------------------------------

def _init_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS facilities (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            name                    TEXT NOT NULL,
            accepted_materials      TEXT NOT NULL,
            total_capacity_tons     REAL NOT NULL,
            used_capacity_tons      REAL NOT NULL DEFAULT 0,
            remaining_capacity_tons REAL NOT NULL,
            status                  TEXT NOT NULL DEFAULT 'OPEN',
            zone                    TEXT NOT NULL,
            data_label              TEXT NOT NULL DEFAULT 'SIMULATED'
        );

        CREATE TABLE IF NOT EXISTS waste_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_input       TEXT,
            waste_type      TEXT NOT NULL,
            quantity_tons   REAL NOT NULL,
            origin          TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS allocations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id      INTEGER,
            facility_id     INTEGER DEFAULT NULL,
            waste_type      TEXT NOT NULL,
            quantity_tons   REAL NOT NULL,
            origin          TEXT NOT NULL,
            allocated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status          TEXT NOT NULL DEFAULT 'ALLOCATED'
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'citizen',
            full_name TEXT,
            phone TEXT,
            area TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS waste_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            waste_category TEXT NOT NULL,
            description TEXT,
            quantity_estimate TEXT,
            severity TEXT NOT NULL DEFAULT 'medium',
            priority TEXT NOT NULL DEFAULT 'normal',
            location_area TEXT NOT NULL,
            location_details TEXT,
            latitude REAL,
            longitude REAL,
            image_path TEXT,
            status TEXT NOT NULL DEFAULT 'Reported',
            ai_category TEXT,
            ai_severity TEXT,
            ai_priority TEXT,
            ai_recommended_action TEXT,
            ai_analysis_done INTEGER NOT NULL DEFAULT 0,
            assigned_to INTEGER,
            collection_date TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'info',
            is_read INTEGER NOT NULL DEFAULT 0,
            related_report_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            action TEXT NOT NULL,
            input_data TEXT,
            output_data TEXT,
            report_id TEXT,
            user_id INTEGER,
            status TEXT NOT NULL DEFAULT 'success',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            old_status TEXT,
            new_status TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS waste_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            color_code TEXT DEFAULT '#6b7280',
            icon TEXT DEFAULT '🗑️',
            is_active INTEGER NOT NULL DEFAULT 1
        );
    """)
    conn.commit()


def _seed_data(conn):
    """Insert simulated facilities and sample data if the table is empty."""
    cursor = conn.execute("SELECT COUNT(*) FROM facilities")
    if cursor.fetchone()[0] > 0:
        return  # already seeded

    conn.executescript("""
        -- ============================================================
        -- SIMULATED DATA — not verified operational BBMP data
        -- For demonstration purposes only (Waste Wise Bengaluru MVP)
        -- ============================================================

        INSERT INTO facilities (name, accepted_materials, total_capacity_tons, used_capacity_tons, remaining_capacity_tons, status, zone, data_label) VALUES
            ('Yelahanka Organic Processing Centre', 'organic,wet',       400.00, 160.00, 240.00, 'OPEN',   'North',      'SIMULATED'),
            ('Bannerghatta Dry Waste Facility',     'dry,plastic',       250.00,  30.00, 220.00, 'OPEN',   'South',      'SIMULATED'),
            ('Whitefield E-Waste Collection Hub',   'e-waste',            80.00,  74.00,   6.00, 'OPEN',   'East',       'SIMULATED'),
            ('Rajajinagar C&D Waste Yard',          'construction',      500.00,  55.00, 445.00, 'OPEN',   'West',       'SIMULATED'),
            ('Shivajinagar Mixed Waste Transfer',   'mixed,organic,dry', 200.00, 100.00, 100.00, 'OPEN',   'Central',    'SIMULATED'),
            ('Hebbal Plastic & Dry Waste Depot',    'plastic,dry',       180.00,  25.00, 155.00, 'OPEN',   'North-East', 'SIMULATED');

        INSERT INTO waste_requests (raw_input, waste_type, quantity_tons, origin) VALUES
            ('Allocate 20 tons of organic waste from Koramangala',  'organic',      20.00, 'Koramangala'),
            ('Send 15 tons of plastic waste from HSR Layout',       'plastic',      15.00, 'HSR Layout'),
            ('Dispose 5 tons of e-waste from Whitefield',           'e-waste',       5.00, 'Whitefield');

        INSERT INTO allocations (request_id, facility_id, waste_type, quantity_tons, origin, status) VALUES
            (1, 1, 'organic', 20.00, 'Koramangala', 'ALLOCATED'),
            (2, 2, 'plastic', 15.00, 'HSR Layout',  'ALLOCATED'),
            (3, 3, 'e-waste',  1.00, 'Whitefield',  'ALLOCATED');
    """)
    conn.commit()


def _seed_demo_data(conn):
    """Seed demo users, waste categories, sample reports and logs if users table is empty."""
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        return  # already seeded

    from werkzeug.security import generate_password_hash

    admin_hash = generate_password_hash("Admin@123")
    citizen_hash = generate_password_hash("Citizen@123")

    # --- Users ---
    conn.execute(
        """INSERT INTO users (username, email, password_hash, role, full_name, area)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("admin", "admin@wastewise.in", admin_hash, "admin", "BBMP Admin", "Central"),
    )
    conn.execute(
        """INSERT INTO users (username, email, password_hash, role, full_name, area)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("citizen1", "citizen1@wastewise.in", citizen_hash, "citizen", "Ravi Kumar", "Koramangala"),
    )
    conn.commit()

    admin_row = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    citizen_row = conn.execute("SELECT id FROM users WHERE username = 'citizen1'").fetchone()
    admin_id = admin_row[0]
    citizen_id = citizen_row[0]

    # --- Waste Categories ---
    categories = [
        ("Organic/Wet", "Food scraps, vegetable peels, garden waste", "#22c55e", "🌿"),
        ("Dry/Recyclable", "Paper, cardboard, glass, metals", "#3b82f6", "♻️"),
        ("E-Waste", "Electronics, batteries, cables, appliances", "#f59e0b", "💻"),
        ("Construction", "Debris, tiles, bricks, sand, cement bags", "#a16207", "🏗️"),
        ("Hazardous", "Chemicals, paints, medical waste, pesticides", "#ef4444", "⚠️"),
        ("Mixed", "Unsorted or unclassified waste", "#6b7280", "🗑️"),
    ]
    for name, desc, color, icon in categories:
        conn.execute(
            """INSERT INTO waste_categories (name, description, color_code, icon)
               VALUES (?, ?, ?, ?)""",
            (name, desc, color, icon),
        )
    conn.commit()

    # --- Sample Waste Reports ---
    sample_reports = [
        ("WR-2024-00001", citizen_id, "Organic/Wet", "Large pile of wet garbage near park entrance",
         "5-10 bags", "high", "high", "Koramangala", "Near Koramangala Park gate 2", "Resolved"),
        ("WR-2024-00002", citizen_id, "Dry/Recyclable", "Cardboard boxes and plastic bottles dumped on roadside",
         "2-3 bags", "medium", "normal", "Koramangala", "80 Feet Road, near petrol station", "Assigned"),
        ("WR-2024-00003", citizen_id, "E-Waste", "Discarded TV and old computer parts",
         "1-2 items", "low", "low", "HSR Layout", "Sector 2, main road", "Reported"),
    ]
    for r in sample_reports:
        conn.execute(
            """INSERT INTO waste_reports
               (report_id, user_id, waste_category, description, quantity_estimate,
                severity, priority, location_area, location_details, status,
                ai_analysis_done)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            r,
        )
    conn.commit()

    # --- Agent Logs ---
    conn.execute(
        """INSERT INTO agent_logs (agent_name, action, input_data, output_data, report_id, user_id, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            "load_intake",
            "analyze_waste_report",
            json.dumps({"waste_category": "Organic/Wet", "location_area": "Koramangala"}),
            json.dumps({"ai_category": "Organic/Wet", "ai_severity": "high", "ai_priority": "high",
                        "ai_recommended_action": "Schedule immediate collection.", "ai_confidence": 0.92}),
            "WR-2024-00001",
            citizen_id,
            "success",
        ),
    )
    conn.commit()

    # --- Notifications ---
    conn.execute(
        """INSERT INTO notifications (user_id, title, message, type, related_report_id)
           VALUES (?, ?, ?, ?, ?)""",
        (citizen_id, "Report Submitted", "Your report WR-2024-00001 has been received.", "info", "WR-2024-00001"),
    )
    conn.execute(
        """INSERT INTO notifications (user_id, title, message, type, related_report_id)
           VALUES (?, ?, ?, ?, ?)""",
        (citizen_id, "Report Resolved", "Your report WR-2024-00001 has been resolved. Thank you!", "success", "WR-2024-00001"),
    )
    conn.execute(
        """INSERT INTO notifications (user_id, title, message, type, related_report_id)
           VALUES (?, ?, ?, ?, ?)""",
        (admin_id, "New Report", "New waste report WR-2024-00003 submitted in HSR Layout.", "info", "WR-2024-00003"),
    )
    conn.commit()


# Auto-initialise on import
def _bootstrap():
    conn = get_connection()
    try:
        _init_schema(conn)
        _seed_data(conn)
        _seed_demo_data(conn)
    finally:
        conn.close()

_bootstrap()


# ---------------------------------------------------------------------------
# Facilities
# ---------------------------------------------------------------------------

def get_all_facilities():
    """Return all facilities as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM facilities ORDER BY id")
        return [_row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_facility_by_id(facility_id):
    """Return a single facility dict, or None if not found."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,))
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_facility_capacity(facility_id, delta_tons):
    """
    Subtract delta_tons from remaining_capacity_tons and add to used_capacity_tons.
    Raises ValueError if the result would be negative.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT remaining_capacity_tons FROM facilities WHERE id = ?", (facility_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Facility {facility_id} not found")
        remaining = float(row[0])
        if remaining - delta_tons < -0.0001:   # tiny float tolerance
            raise ValueError(
                f"Insufficient capacity: facility {facility_id} has {remaining:.2f}t remaining, "
                f"but {delta_tons:.2f}t were requested"
            )
        conn.execute(
            """UPDATE facilities
               SET remaining_capacity_tons = remaining_capacity_tons - ?,
                   used_capacity_tons      = used_capacity_tons      + ?
               WHERE id = ?""",
            (delta_tons, delta_tons, facility_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def revert_facility_capacity(facility_id, delta_tons):
    """
    Add delta_tons back to remaining_capacity_tons, subtract from used_capacity_tons.
    Used when re-planning after a facility closure.
    """
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE facilities
               SET remaining_capacity_tons = remaining_capacity_tons + ?,
                   used_capacity_tons      = used_capacity_tons      - ?
               WHERE id = ?""",
            (delta_tons, delta_tons, facility_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_facility_status(facility_id, status):
    """Update a facility's status to 'OPEN' or 'CLOSED'."""
    if status not in ("OPEN", "CLOSED"):
        raise ValueError("status must be 'OPEN' or 'CLOSED'")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE facilities SET status = ? WHERE id = ?", (status, facility_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Waste requests
# ---------------------------------------------------------------------------

def insert_waste_request(raw_input, waste_type, quantity_tons, origin):
    """Insert a new waste request and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO waste_requests (raw_input, waste_type, quantity_tons, origin) VALUES (?, ?, ?, ?)",
            (raw_input, waste_type, quantity_tons, origin),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Allocations
# ---------------------------------------------------------------------------

def insert_allocation(request_id, facility_id, waste_type, quantity_tons, origin, status="ALLOCATED"):
    """Insert an allocation record and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO allocations (request_id, facility_id, waste_type, quantity_tons, origin, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (request_id, facility_id, waste_type, quantity_tons, origin, status),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_allocation_status(allocation_id, status):
    """Update the status of an allocation record."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE allocations SET status = ? WHERE id = ?", (status, allocation_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_allocations_for_facility(facility_id):
    """Return all ALLOCATED allocations for a facility as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM allocations WHERE facility_id = ? AND status = 'ALLOCATED'",
            (facility_id,),
        )
        return [_row_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

def get_dashboard_stats():
    """
    Return aggregated dashboard statistics.
    """
    conn = get_connection()
    try:
        total_requests = conn.execute("SELECT COUNT(*) FROM waste_requests").fetchone()[0]

        total_allocated_tons = float(
            conn.execute(
                "SELECT COALESCE(SUM(quantity_tons), 0) FROM allocations WHERE status = 'ALLOCATED'"
            ).fetchone()[0]
        )

        total_unallocated_tons = float(
            conn.execute(
                "SELECT COALESCE(SUM(quantity_tons), 0) FROM allocations WHERE status = 'UNALLOCATED'"
            ).fetchone()[0]
        )

        open_facilities = conn.execute(
            "SELECT COUNT(*) FROM facilities WHERE status = 'OPEN'"
        ).fetchone()[0]

        closed_facilities = conn.execute(
            "SELECT COUNT(*) FROM facilities WHERE status = 'CLOSED'"
        ).fetchone()[0]

        facilities = [
            _row_to_dict(r)
            for r in conn.execute("SELECT * FROM facilities ORDER BY id").fetchall()
        ]

        return {
            "total_requests": total_requests,
            "total_allocated_tons": total_allocated_tons,
            "total_unallocated_tons": total_unallocated_tons,
            "open_facilities": open_facilities,
            "closed_facilities": closed_facilities,
            "facilities": facilities,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def create_user(username, email, password_hash, role='citizen', full_name='', phone='', area=''):
    """Insert a new user and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO users (username, email, password_hash, role, full_name, phone, area)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, email, password_hash, role, full_name, phone, area),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Return a user dict by id, or None."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_user_by_username(username):
    """Return a user dict by username, or None."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_user_by_email(email):
    """Return a user dict by email, or None."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_user_last_login(user_id):
    """Update the last_login timestamp for a user."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_users():
    """Return all users as a list of dicts."""
    conn = get_connection()
    try:
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]
    finally:
        conn.close()


def set_user_active(user_id, is_active):
    """Enable or disable a user account."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Waste Reports
# ---------------------------------------------------------------------------

def generate_report_id():
    """Generate a unique report id in the format WR-YYYY-NNNNN."""
    conn = get_connection()
    try:
        year = datetime.now().year
        count = conn.execute("SELECT COUNT(*) FROM waste_reports").fetchone()[0]
        return f"WR-{year}-{count + 1:05d}"
    finally:
        conn.close()


def insert_waste_report(user_id, waste_category, description, quantity_estimate,
                        severity, priority, location_area, location_details, image_path=None):
    """Insert a new waste report and return the full report dict."""
    report_id = generate_report_id()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO waste_reports
               (report_id, user_id, waste_category, description, quantity_estimate,
                severity, priority, location_area, location_details, image_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_id, user_id, waste_category, description, quantity_estimate,
             severity, priority, location_area, location_details, image_path),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM waste_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
        return _row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_all_reports(limit=100, offset=0):
    """Return a paginated list of all waste reports."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM waste_reports ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_reports_by_user(user_id):
    """Return all waste reports submitted by a specific user."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM waste_reports WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_report_by_id(report_id):
    """Return a waste report dict by report_id string, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM waste_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_report_status(report_id, new_status, updated_by_user_id=None, notes=None):
    """Update the status (and optional notes) of a waste report."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE waste_reports
               SET status = ?, notes = COALESCE(?, notes),
                   updated_at = CURRENT_TIMESTAMP
               WHERE report_id = ?""",
            (new_status, notes, report_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_report_ai_analysis(report_id, ai_category, ai_severity, ai_priority, ai_action):
    """Persist the AI analysis result fields on a waste report."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE waste_reports
               SET ai_category = ?, ai_severity = ?, ai_priority = ?,
                   ai_recommended_action = ?, ai_analysis_done = 1,
                   updated_at = CURRENT_TIMESTAMP
               WHERE report_id = ?""",
            (ai_category, ai_severity, ai_priority, ai_action, report_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_report_stats():
    """Return aggregated stats: total, by_status, by_category, by_severity, recent_7_days."""
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM waste_reports").fetchone()[0]

        by_status = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT status, COUNT(*) FROM waste_reports GROUP BY status"
            ).fetchall()
        }

        by_category = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT waste_category, COUNT(*) FROM waste_reports GROUP BY waste_category"
            ).fetchall()
        }

        by_severity = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT severity, COUNT(*) FROM waste_reports GROUP BY severity"
            ).fetchall()
        }

        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        recent_7_days = conn.execute(
            "SELECT COUNT(*) FROM waste_reports WHERE created_at >= ?", (cutoff,)
        ).fetchone()[0]

        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
            "by_severity": by_severity,
            "recent_7_days": recent_7_days,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def create_notification(user_id, title, message, notif_type='info', related_report_id=None):
    """Insert a notification for a user and return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO notifications (user_id, title, message, type, related_report_id)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, title, message, notif_type, related_report_id),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_notifications_for_user(user_id, unread_only=False):
    """Return notifications for a user, optionally filtering to unread only."""
    conn = get_connection()
    try:
        if unread_only:
            rows = conn.execute(
                "SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def mark_notification_read(notif_id):
    """Mark a single notification as read."""
    conn = get_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_all_notifications_read(user_id):
    """Mark all notifications for a user as read."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_unread_count(user_id):
    """Return the count of unread notifications for a user."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Agent Logs
# ---------------------------------------------------------------------------

def log_agent_action(agent_name, action, input_data, output_data,
                     report_id=None, user_id=None, status='success'):
    """Insert an agent action log entry."""
    conn = get_connection()
    try:
        if not isinstance(input_data, str):
            input_data = json.dumps(input_data)
        if not isinstance(output_data, str):
            output_data = json.dumps(output_data)
        conn.execute(
            """INSERT INTO agent_logs
               (agent_name, action, input_data, output_data, report_id, user_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_name, action, input_data, output_data, report_id, user_id, status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_agent_logs(limit=50):
    """Return the most recent agent log entries."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------

def log_audit(user_id, username, action, entity_type=None, entity_id=None,
              old_status=None, new_status=None, details=None, ip_address=None):
    """Insert an audit log entry."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO audit_logs
               (user_id, username, action, entity_type, entity_id,
                old_status, new_status, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, action, entity_type, entity_id,
             old_status, new_status, details, ip_address),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_audit_logs(limit=100):
    """Return the most recent audit log entries."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_audit_logs_for_report(report_id):
    """Return audit log entries for a specific report (entity_id match)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_logs WHERE entity_type = 'report' AND entity_id = ? ORDER BY created_at DESC",
            (str(report_id),),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
