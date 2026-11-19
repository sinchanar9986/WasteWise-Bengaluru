"""
Load Intake Agent
=================
Parses a natural-language or structured waste request into:
  {waste_type, quantity_tons, origin}

Primary path : IBM Granite via watsonx.ai REST API.
Fallback path: regex extraction when Granite is unavailable.
"""

import os
import re
import json
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_WASTE_TYPES = ["organic", "plastic", "e-waste", "construction", "wet", "dry", "mixed"]

IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
WATSONX_API_VERSION = "2023-05-29"

PROMPT_TEMPLATE = (
    'Extract waste allocation details from the following request.\n'
    'Return ONLY valid JSON in this exact format: '
    '{{"waste_type": "...", "quantity_tons": <number>, "origin": "..."}}\n'
    'waste_type must be one of: organic, plastic, e-waste, construction, wet, dry, mixed\n'
    'quantity_tons must be a positive number.\n\n'
    'Request: "{user_input}"\n\n'
    'JSON:'
)

# ---------------------------------------------------------------------------
# IAM token
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


# ---------------------------------------------------------------------------
# Granite LLM call
# ---------------------------------------------------------------------------


def _call_granite(prompt: str) -> dict:
    """
    Call IBM Granite via watsonx.ai and return the parsed JSON dict.
    Raises an exception on any failure so the caller can fall back to regex.
    """
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

    generated_text = resp.json()["results"][0]["generated_text"].strip()

    # Granite may wrap the JSON in markdown fences — strip them if present
    if generated_text.startswith("```"):
        generated_text = re.sub(r"```[a-z]*", "", generated_text).replace("```", "").strip()

    return json.loads(generated_text)


# ---------------------------------------------------------------------------
# Regex fallback
# ---------------------------------------------------------------------------


def _regex_extract(raw_input: str) -> dict:
    """
    Best-effort extraction using regex patterns.
    Returns a dict with waste_type, quantity_tons, origin (may be None/0 on failure).
    """
    # Quantity: first integer or decimal number in the string
    qty_match = re.search(r"\b(\d+(?:\.\d+)?)\b", raw_input)
    quantity_tons = float(qty_match.group(1)) if qty_match else 0.0

    # Waste type: first occurrence of a known keyword (case-insensitive)
    waste_type = None
    lower_input = raw_input.lower()
    for wt in KNOWN_WASTE_TYPES:
        if wt in lower_input:
            waste_type = wt
            break

    # Origin: text following "from " (one or more words)
    origin_match = re.search(r"\bfrom\s+([A-Za-z][A-Za-z\s]+?)(?:\s*$|[,.])", raw_input, re.IGNORECASE)
    origin = origin_match.group(1).strip() if origin_match else "Unknown"

    return {"waste_type": waste_type, "quantity_tons": quantity_tons, "origin": origin}


# ---------------------------------------------------------------------------
# Guardrails (shared by both parse paths)
# ---------------------------------------------------------------------------


def _apply_guardrails(waste_type, quantity_tons, origin) -> dict | None:
    """
    Validate parsed fields.
    Returns an error dict if validation fails, None if everything is fine.
    """
    if quantity_tons <= 0:
        return {"error": "Quantity must be greater than zero"}

    if waste_type not in KNOWN_WASTE_TYPES:
        return {
            "error": f"Unknown waste type '{waste_type}'. Must be one of: {KNOWN_WASTE_TYPES}"
        }

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_waste_request(raw_input: str) -> dict:
    """
    Parse a natural-language waste request.

    Returns on success:
        {"waste_type": str, "quantity_tons": float, "origin": str, "method": "granite"|"regex"}
    Returns on failure:
        {"error": str}
    """
    parsed = None
    method = "granite"

    # --- Granite path ---
    try:
        prompt = PROMPT_TEMPLATE.format(user_input=raw_input)
        parsed = _call_granite(prompt)
    except Exception as exc:
        logger.warning("Granite unavailable (%s); falling back to regex.", exc)
        method = "regex"

    # --- Regex fallback ---
    if parsed is None:
        parsed = _regex_extract(raw_input)

    # Normalise types
    waste_type = str(parsed.get("waste_type") or "").lower().strip()
    origin = str(parsed.get("origin") or "").strip() or "Unknown"
    try:
        quantity_tons = float(parsed.get("quantity_tons", 0))
    except (TypeError, ValueError):
        quantity_tons = 0.0

    # Guardrails
    error = _apply_guardrails(waste_type, quantity_tons, origin)
    if error:
        return error

    return {
        "waste_type": waste_type,
        "quantity_tons": quantity_tons,
        "origin": origin,
        "method": method,
    }


def validate_structured_input(waste_type: str, quantity_tons: float, origin: str) -> dict:
    """
    Validate directly supplied structured fields with the same guardrails as parse_waste_request.

    Returns on success:
        {"waste_type": str, "quantity_tons": float, "origin": str, "method": "structured"}
    Returns on failure:
        {"error": str}
    """
    waste_type = str(waste_type or "").lower().strip()
    origin = str(origin or "").strip() or "Unknown"
    try:
        quantity_tons = float(quantity_tons)
    except (TypeError, ValueError):
        quantity_tons = 0.0

    error = _apply_guardrails(waste_type, quantity_tons, origin)
    if error:
        return error

    return {
        "waste_type": waste_type,
        "quantity_tons": quantity_tons,
        "origin": origin,
        "method": "structured",
    }
