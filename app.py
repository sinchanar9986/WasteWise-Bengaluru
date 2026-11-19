"""
app.py — Flask application entry point for Waste Wise Bengaluru.
Run with: python app.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, render_template
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv

from agents import load_intake, capacity_allocator, scenario_analyst
import db as db_module
from auth.user_model import User

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'wwb-dev-secret-change-in-production')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max upload
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------------------------------------------------------------------------
# Flask-Login
# ---------------------------------------------------------------------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    user_dict = db_module.get_user_by_id(int(user_id))
    return User(user_dict) if user_dict else None


# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------

from auth.routes import auth_bp
from routes.citizen import citizen_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(citizen_bp)
app.register_blueprint(admin_bp)

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Not found"}), 404
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": str(e)}), 500
    return render_template('errors/500.html'), 500


# ---------------------------------------------------------------------------
# Top-level navigation routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('citizen.dashboard'))


@app.route('/legacy')
def legacy():
    workspace = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(workspace, 'index.html')


# ---------------------------------------------------------------------------
# Real data routes
# ---------------------------------------------------------------------------

@app.route("/api/facilities", methods=["GET"])
def get_facilities():
    """Return current state of all facilities."""
    try:
        facilities = db_module.get_all_facilities()
        return jsonify({"success": True, "facilities": facilities})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Return aggregated dashboard statistics."""
    try:
        stats = db_module.get_dashboard_stats()
        return jsonify({"success": True, **stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/notifications/unread-count", methods=["GET"])
@login_required
def notifications_unread_count():
    """Return unread notification count for the logged-in user."""
    try:
        count = db_module.get_unread_count(current_user.id)
        return jsonify({"success": True, "count": count})
    except Exception as e:
        return jsonify({"success": False, "count": 0, "error": str(e)}), 500


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
        request_id = db_module.insert_waste_request(raw_input, wt, qty, orig)
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
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
