"""
Scenario Analysis Agent
=======================
Provides two capabilities:
  1. Plain-English explanation of an allocation decision (Granite LLM + template fallback).
  2. Facility closure detection and re-planning via replan_after_closure().

Public API
----------
  explain_allocation(allocation_result: dict) -> str
  explain_rejection(reason: str, waste_type: str, quantity_tons: float, origin: str) -> str
  replan_after_closure(facility_id: int) -> dict
"""

import os
import sys
import logging

import requests
from dotenv import load_dotenv

# Allow importing db from the project root when running from agents/ or via Flask.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (same watsonx.ai coordinates used by load_intake.py)
# ---------------------------------------------------------------------------

IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
WATSONX_API_VERSION = "2023-05-29"

EXPLANATION_PROMPT_TEMPLATE = (
    "You are an AI assistant for Bengaluru's waste management system.\n"
    "Given this waste allocation result, write a clear 2-3 sentence explanation for a city official.\n"
    "Be factual and concise. Do not add information not present in the data.\n\n"
    "Allocation Result:\n"
    "- Waste Type: {waste_type}\n"
    "- Requested Quantity: {quantity_tons} tons from {origin}\n"
    "- Allocated Quantity: {allocated_tons} tons\n"
    "- Unallocated Quantity: {unallocated_tons} tons\n"
    "- Facility: {facility_name}\n"
    "- Decision: {decision}\n\n"
    "Explanation:"
)

# ---------------------------------------------------------------------------
# IAM token + Granite helper (mirrors load_intake.py exactly)
# ---------------------------------------------------------------------------


def _get_iam_token(api_key: str) -> str:
    """Exchange a watsonx API key for a short-lived IAM Bearer token."""
    resp = requests.post(
        IAM_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _call_granite_for_explanation(prompt: str) -> str:
    """
    Call IBM Granite via watsonx.ai and return the generated text string.
    Returns an empty string on any failure so the caller can use a template fallback.
    """
    try:
        api_key = os.environ.get("WATSONX_API_KEY", "")
        project_id = os.environ.get("WATSONX_PROJECT_ID", "")
        base_url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").rstrip("/")

        if not api_key or not project_id:
            raise ValueError("WATSONX_API_KEY and WATSONX_PROJECT_ID must be set")

        token = _get_iam_token(api_key)

        endpoint = f"{base_url}/ml/v1/text/generation?version={WATSONX_API_VERSION}"
        payload = {
            "model_id": "ibm/granite-3-8b-instruct",
            "input": prompt,
            "parameters": {"max_new_tokens": 150, "temperature": 0},
            "project_id": project_id,
        }

        resp = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["results"][0]["generated_text"].strip()

    except Exception as exc:
        logger.warning("Granite unavailable for explanation (%s); using template fallback.", exc)
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def explain_allocation(allocation_result: dict) -> str:
    """
    Generate a 2-3 sentence plain-English explanation of an allocation decision.
    Uses Granite LLM; falls back to a template string when Granite is unavailable.

    Parameters
    ----------
    allocation_result : dict
        The dict returned by capacity_allocator.allocate().
    """
    waste_type = allocation_result.get("waste_type") or (
        allocation_result.get("facility") or {}
    ).get("waste_type", "unknown")
    # Prefer top-level fields written by the caller; derive from facility if absent.
    allocated_tons = float(allocation_result.get("allocated_tons", 0))
    unallocated_tons = float(allocation_result.get("unallocated_tons", 0))
    quantity_tons = allocated_tons + unallocated_tons
    origin = allocation_result.get("origin", "Unknown")
    facility = allocation_result.get("facility") or {}
    facility_name = facility.get("name", "N/A")
    success = allocation_result.get("success", False)
    error = allocation_result.get("error") or ""

    # Derive remaining capacity after allocation (if available in facility snapshot)
    remaining = float(facility.get("remaining_capacity_tons", 0))

    # Determine decision label
    if not success:
        decision = "Rejected"
    elif unallocated_tons == 0:
        decision = "Full allocation"
    else:
        decision = "Partial allocation"

    # --- Granite path ---
    prompt = EXPLANATION_PROMPT_TEMPLATE.format(
        waste_type=waste_type,
        quantity_tons=quantity_tons,
        origin=origin,
        allocated_tons=allocated_tons,
        unallocated_tons=unallocated_tons,
        facility_name=facility_name,
        decision=decision,
    )
    generated = _call_granite_for_explanation(prompt)
    if generated:
        return generated

    # --- Template fallback ---
    if decision == "Full allocation":
        return (
            f"{allocated_tons} tons of {waste_type} waste from {origin} has been successfully "
            f"allocated to {facility_name}. The facility has {remaining} tons of capacity "
            f"remaining after this allocation."
        )
    if decision == "Partial allocation":
        return (
            f"{allocated_tons} tons of {waste_type} waste from {origin} has been allocated to "
            f"{facility_name}. {unallocated_tons} tons could not be allocated due to insufficient "
            f"remaining capacity across all compatible facilities."
        )
    # Rejected
    return (
        f"The request to allocate {quantity_tons} tons of {waste_type} waste from {origin} could "
        f"not be fulfilled. Reason: {error}"
    )


def explain_rejection(reason: str, waste_type: str, quantity_tons: float, origin: str) -> str:
    """
    Return a template-only explanation for a rejected allocation request.
    No LLM call needed for simple rejections.
    """
    return (
        f"Allocation rejected: {reason}. "
        f"The request was for {quantity_tons} tons of {waste_type} waste from {origin}."
    )


def replan_after_closure(facility_id: int) -> dict:
    """
    Mark a facility as CLOSED and re-allocate all of its ALLOCATED waste.

    Returns a structured dict with:
        success, closed_facility, affected_allocations, new_allocations,
        total_reallocated_tons, total_unallocated_tons, explanation, stages
    """
    # Import here to avoid circular imports (capacity_allocator imports db at module level).
    from agents import capacity_allocator  # noqa: PLC0415

    # Step 1 — Fetch facility
    facility = db.get_facility_by_id(facility_id)
    if facility is None:
        return {
            "success": False,
            "error": f"Facility {facility_id} not found",
            "stages": [],
        }

    if str(facility.get("status", "")).upper() == "CLOSED":
        return {
            "success": False,
            "error": f"Facility '{facility['name']}' is already CLOSED",
            "stages": [],
        }

    # Step 2 — Fetch affected ALLOCATED allocations (before closing)
    affected_allocations = db.get_allocations_for_facility(facility_id)

    # Step 3 — Mark facility CLOSED
    db.set_facility_status(facility_id, "CLOSED")

    stages = [
        {
            "stage": "Facility Closed",
            "detail": f"Facility '{facility['name']}' has been marked CLOSED",
        },
        {
            "stage": "Affected Allocations Identified",
            "detail": (
                f"{len(affected_allocations)} allocation(s) "
                f"({sum(float(a.get('quantity_tons', 0)) for a in affected_allocations):.2f} tons) affected"
            ),
        },
        {
            "stage": "Re-planning",
            "detail": "Attempting reallocation to compatible open facilities",
        },
    ]

    # Step 4 — Re-allocate each affected allocation
    new_allocations = []
    total_reallocated = 0.0
    total_unallocated = 0.0

    for allocation in affected_allocations:
        alloc_id = allocation["id"]
        qty = float(allocation.get("quantity_tons", 0))
        waste_type = allocation.get("waste_type", "")
        origin = allocation.get("origin", "Unknown")
        request_id = allocation.get("request_id")

        # Revert capacity on the closed facility (audit trail)
        db.revert_facility_capacity(facility_id, qty)

        # Mark old allocation as REALLOCATED
        db.update_allocation_status(alloc_id, "REALLOCATED")

        # Attempt re-allocation via the capacity allocator
        new_result = capacity_allocator.allocate(waste_type, qty, origin, request_id)
        # Attach original context so explain_allocation has what it needs
        new_result.setdefault("waste_type", waste_type)
        new_result.setdefault("origin", origin)
        new_allocations.append(new_result)

        total_reallocated += float(new_result.get("allocated_tons", 0))
        total_unallocated += float(new_result.get("unallocated_tons", 0))

    stages.append(
        {
            "stage": "New Allocations",
            "detail": (
                f"{total_reallocated:.2f} tons reallocated, "
                f"{total_unallocated:.2f} tons unallocated"
            ),
        }
    )

    # Step 5 — Build a summary result dict for the explanation
    summary_result = {
        "success": total_unallocated == 0,
        "waste_type": "mixed",  # summary across all waste types
        "origin": "multiple zones",
        "allocated_tons": total_reallocated,
        "unallocated_tons": total_unallocated,
        "facility": new_allocations[0].get("facility") if new_allocations else None,
        "error": None if total_unallocated == 0 else "Insufficient capacity across remaining facilities",
    }
    explanation = explain_allocation(summary_result)

    return {
        "success": True,
        "closed_facility": facility,
        "affected_allocations": affected_allocations,
        "new_allocations": new_allocations,
        "total_reallocated_tons": total_reallocated,
        "total_unallocated_tons": total_unallocated,
        "explanation": explanation,
        "stages": stages,
    }
