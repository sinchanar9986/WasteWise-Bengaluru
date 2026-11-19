"""
app.py — Flask application entry point for Waste Wise Bengaluru.
Run with: python app.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from agents import load_intake, capacity_allocator, scenario_analyst
import db

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

@app.errorhandler(Exception)
def handle_error(e):
    return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

@app.route("/")
def serve_index():
    """Serve the single-page frontend dashboard."""
    workspace = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(workspace, "index.html")


# ---------------------------------------------------------------------------
# Real data routes
# ---------------------------------------------------------------------------

@app.route("/api/facilities", methods=["GET"])
def get_facilities():
    """Return current state of all facilities."""
    try:
        facilities = db.get_all_facilities()
        return jsonify({"success": True, "facilities": facilities})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Return aggregated dashboard statistics."""
    try:
        stats = db.get_dashboard_stats()
        return jsonify({"success": True, **stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Agent-backed routes
# ---------------------------------------------------------------------------

@app.route("/api/allocate", methods=["POST"])
def allocate():
    """Parse + allocate a waste request via load_intake → capacity_allocator → scenario_analyst."""
    try:
        body = request.get_json(silent=True) or {}

        raw_input = body.get("raw_input")
        waste_type = body.get("waste_type")
        quantity_tons = body.get("quantity_tons")
        origin = body.get("origin")

        # Determine intake mode
        if raw_input is not None:
            intake = load_intake.parse_waste_request(raw_input)
        elif waste_type is not None and quantity_tons is not None and origin is not None:
            intake = load_intake.validate_structured_input(waste_type, quantity_tons, origin)
            raw_input = f"{quantity_tons} tons of {waste_type} waste from {origin}"
        else:
            return jsonify({
                "success": False,
                "error": "Provide either 'raw_input' or all of 'waste_type', 'quantity_tons', 'origin'",
            }), 400

        # Intake error (guardrail failure)
        if "error" in intake:
            return jsonify({"success": False, "error": intake["error"]}), 400

        wt = intake["waste_type"]
        qty = intake["quantity_tons"]
        orig = intake["origin"]

        # Insert waste request and allocate
        request_id = db.insert_waste_request(raw_input, wt, qty, orig)
        result = capacity_allocator.allocate(wt, qty, orig, request_id)

        # Attach intake context so explain_allocation can derive waste_type / origin
        result.setdefault("waste_type", wt)
        result.setdefault("origin", orig)

        explanation = scenario_analyst.explain_allocation(result)
        comparison = capacity_allocator.compare_approaches(wt, qty)

        return jsonify({
            "success": True,
            "intake": intake,
            "allocation": result,
            "explanation": explanation,
            "comparison": comparison,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/close-facility", methods=["POST"])
def close_facility():
    """Close a facility and trigger re-planning for all its allocations."""
    try:
        body = request.get_json(silent=True) or {}
        facility_id = body.get("facility_id")
        if facility_id is None:
            return jsonify({"success": False, "error": "'facility_id' is required"}), 400

        result = scenario_analyst.replan_after_closure(int(facility_id))

        if not result.get("success") and "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/replan", methods=["POST"])
def replan():
    """Manually trigger re-planning for a facility (same logic as /api/close-facility)."""
    try:
        body = request.get_json(silent=True) or {}
        facility_id = body.get("facility_id")
        if facility_id is None:
            return jsonify({"success": False, "error": "'facility_id' is required"}), 400

        result = scenario_analyst.replan_after_closure(int(facility_id))

        if not result.get("success") and "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/compare", methods=["POST"])
def compare():
    """Compare first-compatible vs capacity-aware allocation strategies (read-only)."""
    try:
        body = request.get_json(silent=True) or {}
        waste_type = body.get("waste_type")
        quantity_tons = body.get("quantity_tons")

        if waste_type is None or quantity_tons is None:
            return jsonify({
                "success": False,
                "error": "'waste_type' and 'quantity_tons' are required",
            }), 400

        comparison = capacity_allocator.compare_approaches(str(waste_type), float(quantity_tons))
        return jsonify({"success": True, "comparison": comparison})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
