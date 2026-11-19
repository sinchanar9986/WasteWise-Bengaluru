"""
agents/capacity_allocator.py — Capacity Allocation Agent for Waste Wise Bengaluru.

Pure-Python deterministic engine. No LLM calls here.
All capacity arithmetic is performed in Python; the LLM never touches numbers.

Guarantees enforced:
  - Never allocates to a closed facility.
  - Never allocates to an incompatible facility.
  - Never allocates beyond available remaining capacity.
  - Never produces negative capacity.
"""

import sys
import os

# Allow importing db from the project root when this module is executed
# directly or via Flask (which runs from the root directory).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


# ---------------------------------------------------------------------------
# Compatible facilities query
# ---------------------------------------------------------------------------

def get_compatible_facilities(waste_type: str) -> list:
    """
    Return all OPEN facilities whose accepted_materials contains waste_type
    (case-insensitive substring match performed in Python after fetching).
    """
    all_facilities = db.get_all_facilities()
    waste_type_lower = waste_type.strip().lower()
    compatible = []
    for facility in all_facilities:
        if facility.get("status", "").upper() != "OPEN":
            continue
        accepted = facility.get("accepted_materials", "") or ""
        # accepted_materials is a comma-separated string, e.g. "organic,wet,mixed"
        accepted_lower = [m.strip().lower() for m in accepted.split(",")]
        if waste_type_lower in accepted_lower:
            compatible.append(facility)
    return compatible


# ---------------------------------------------------------------------------
# Selection strategies
# ---------------------------------------------------------------------------

def first_compatible_select(facilities: list, quantity_tons: float):
    """
    Return the first facility in *facilities* that has any remaining capacity
    (remaining_capacity_tons > 0).  Does NOT require the facility to fit the
    full quantity — just the first with space.

    Returns a facility dict, or None if the list is empty or all are full.
    """
    for facility in facilities:
        if float(facility.get("remaining_capacity_tons", 0)) > 0:
            return facility
    return None


def capacity_aware_select(facilities: list, quantity_tons: float):
    """
    Choose the best facility using a two-tier algorithm:

    Tier 1 — facilities where remaining_capacity_tons >= quantity_tons:
              pick the one with the highest remaining_capacity_tons
              (most headroom; lowest utilisation pressure).

    Tier 2 — if no facility can fit the full quantity:
              pick the facility with the highest remaining_capacity_tons overall
              (best partial allocation).

    Returns a facility dict, or None if *facilities* is empty.
    """
    if not facilities:
        return None

    can_fit = [
        f for f in facilities
        if float(f.get("remaining_capacity_tons", 0)) >= quantity_tons
    ]

    if can_fit:
        return max(can_fit, key=lambda f: float(f.get("remaining_capacity_tons", 0)))

    # No facility can fully accommodate — partial allocation with most remaining
    return max(facilities, key=lambda f: float(f.get("remaining_capacity_tons", 0)))


# ---------------------------------------------------------------------------
# Main allocation function
# ---------------------------------------------------------------------------

def allocate(
    waste_type: str,
    quantity_tons: float,
    origin: str,
    request_id: int = None,
) -> dict:
    """
    Perform a capacity-aware allocation with full DB writes.

    Returns:
        {
            "success": bool,
            "allocated_tons": float,
            "unallocated_tons": float,
            "facility": dict | None,
            "allocation_id": int | None,
            "decision_trace": list[dict],
            "approach": "capacity_aware",
            "error": str | None,
        }
    """
    trace = []

    def _step(step, status, detail):
        trace.append({"step": step, "status": status, "detail": detail})

    def _fail(error_msg):
        return {
            "success": False,
            "allocated_tons": 0.0,
            "unallocated_tons": float(quantity_tons) if isinstance(quantity_tons, (int, float)) else 0.0,
            "facility": None,
            "allocation_id": None,
            "decision_trace": trace,
            "approach": "capacity_aware",
            "error": error_msg,
        }

    # Step 1 — Waste type identification
    _step("Waste Type Identification", "✓", f"Identified waste type: {waste_type}")

    # Step 2 — Quantity validation
    try:
        qty = float(quantity_tons)
    except (TypeError, ValueError):
        _step("Quantity Validation", "✗", f"Invalid quantity value: {quantity_tons!r}")
        return _fail(f"Invalid quantity: {quantity_tons!r}")

    if qty <= 0:
        _step("Quantity Validation", "✗", f"Quantity must be > 0, got {qty}")
        return _fail(f"Quantity must be greater than 0 (got {qty})")

    _step("Quantity Validation", "✓", f"Quantity: {qty} tons")

    # Step 3 — Origin recorded
    _step("Origin Recorded", "✓", f"Origin: {origin}")

    # Step 4 — Compatible facilities search
    facilities = get_compatible_facilities(waste_type)

    if not facilities:
        _step(
            "Compatible Facilities Search",
            "✗",
            f"No open facilities accept '{waste_type}' waste",
        )
        return _fail(f"No open facilities accept '{waste_type}' waste")

    _step(
        "Compatible Facilities Search",
        "✓",
        f"Found {len(facilities)} compatible open "
        f"{'facility' if len(facilities) == 1 else 'facilities'}",
    )

    # Step 5 — Facility selection
    selected = capacity_aware_select(facilities, qty)

    if selected is None:
        _step("Facility Selection", "✗", "No facility with remaining capacity found")
        return _fail("No facility with remaining capacity found")

    remaining = float(selected.get("remaining_capacity_tons", 0))
    _step(
        "Facility Selection",
        "✓",
        f"Selected: {selected['name']} ({remaining}t remaining)",
    )

    # Step 6 — Capacity check & determine actual allocation
    if remaining < qty:
        actual_allocated = remaining
        unallocated = round(qty - actual_allocated, 6)
        _step(
            "Capacity Check",
            "✗",
            f"Only {remaining}t available — partial allocation "
            f"({actual_allocated}t allocated, {unallocated}t unallocated)",
        )
    else:
        actual_allocated = qty
        unallocated = 0.0
        _step(
            "Capacity Check",
            "✓",
            f"Requested {qty}t ≤ {remaining}t available",
        )

    # Step 7 — Allocation
    _step(
        "Allocation",
        "✓",
        f"Allocated {actual_allocated}t to {selected['name']}",
    )

    # DB writes
    facility_id = selected["id"]
    db.update_facility_capacity(facility_id, actual_allocated)

    allocation_id = db.insert_allocation(
        request_id, facility_id, waste_type, actual_allocated, origin, status="ALLOCATED"
    )

    if unallocated > 0:
        db.insert_allocation(
            request_id, None, waste_type, unallocated, origin, status="UNALLOCATED"
        )

    return {
        "success": True,
        "allocated_tons": actual_allocated,
        "unallocated_tons": unallocated,
        "facility": selected,
        "allocation_id": allocation_id,
        "decision_trace": trace,
        "approach": "capacity_aware",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Read-only approach comparison
# ---------------------------------------------------------------------------

def compare_approaches(waste_type: str, quantity_tons: float) -> dict:
    """
    Read-only snapshot comparison between first_compatible and capacity_aware
    selection strategies.  Makes NO DB writes.

    Returns:
        {
            "first_compatible": {
                "facility_name": str,
                "remaining_capacity_tons": float,
                "would_fit_fully": bool,
                "utilization_pct": float,
            },
            "capacity_aware": {
                "facility_name": str,
                "remaining_capacity_tons": float,
                "would_fit_fully": bool,
                "utilization_pct": float,
            },
            "same_facility": bool,
        }
    """
    qty = float(quantity_tons)
    facilities = get_compatible_facilities(waste_type)

    def _summarise(facility):
        if facility is None:
            return {
                "facility_name": "None available",
                "remaining_capacity_tons": 0.0,
                "would_fit_fully": False,
                "utilization_pct": 0.0,
            }
        remaining = float(facility.get("remaining_capacity_tons", 0))
        total = float(facility.get("total_capacity_tons", 0))
        utilization_pct = round(
            ((total - remaining) / total * 100) if total > 0 else 0.0, 2
        )
        return {
            "facility_name": facility["name"],
            "remaining_capacity_tons": remaining,
            "would_fit_fully": remaining >= qty,
            "utilization_pct": utilization_pct,
        }

    fc = first_compatible_select(facilities, qty)
    ca = capacity_aware_select(facilities, qty)

    fc_summary = _summarise(fc)
    ca_summary = _summarise(ca)

    same_facility = (
        fc is not None
        and ca is not None
        and fc["id"] == ca["id"]
    )

    return {
        "first_compatible": fc_summary,
        "capacity_aware": ca_summary,
        "same_facility": same_facility,
    }
