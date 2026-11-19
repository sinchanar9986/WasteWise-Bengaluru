"""
db.py — SQLite connection and query helpers for Waste Wise Bengaluru.
Uses SQLite (zero-install) for the MVP demo.
Credentials/config are loaded from .env via python-dotenv.
"""

import os
import sqlite3
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


# Auto-initialise on import
def _bootstrap():
    conn = get_connection()
    try:
        _init_schema(conn)
        _seed_data(conn)
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
