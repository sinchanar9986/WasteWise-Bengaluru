"""
auth/routes.py — Authentication blueprint (login, register, logout).
"""

import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import db
from auth.user_model import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,20}$')
_PASSWORD_MIN_LEN = 8


def _validate_username(username):
    """Return error string or None."""
    if not username:
        return "Username is required."
    if not _USERNAME_RE.match(username):
        return "Username must be 3–20 characters: letters, numbers, underscores only."
    return None


def _validate_password(password):
    """Return error string or None."""
    if not password or len(password) < _PASSWORD_MIN_LEN:
        return f"Password must be at least {_PASSWORD_MIN_LEN} characters."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('auth/login.html')


@auth_bp.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for('auth.login'))

    user_dict = db.get_user_by_username(username)
    if user_dict is None:
        flash("Invalid username or password.", "error")
        return redirect(url_for('auth.login'))

    if not user_dict.get('is_active', 1):
        flash("Your account has been deactivated. Please contact support.", "error")
        return redirect(url_for('auth.login'))

    if not check_password_hash(user_dict['password_hash'], password):
        flash("Invalid username or password.", "error")
        return redirect(url_for('auth.login'))

    user = User(user_dict)
    login_user(user)
    db.update_user_last_login(user_dict['id'])

    next_page = request.args.get('next')
    return redirect(next_page or url_for('dashboard'))


@auth_bp.route('/register', methods=['GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('auth/register.html')


@auth_bp.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    full_name = request.form.get('full_name', '').strip()
    area = request.form.get('area', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '')
    confirm = request.form.get('confirm_password', '')

    # Validate username
    err = _validate_username(username)
    if err:
        flash(err, "error")
        return redirect(url_for('auth.register'))

    # Validate password
    err = _validate_password(password)
    if err:
        flash(err, "error")
        return redirect(url_for('auth.register'))

    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for('auth.register'))

    if not email or '@' not in email:
        flash("A valid email address is required.", "error")
        return redirect(url_for('auth.register'))

    # Uniqueness checks
    if db.get_user_by_username(username):
        flash("Username already taken. Please choose another.", "error")
        return redirect(url_for('auth.register'))

    if db.get_user_by_email(email):
        flash("An account with this email already exists.", "error")
        return redirect(url_for('auth.register'))

    password_hash = generate_password_hash(password)
    db.create_user(
        username=username,
        email=email,
        password_hash=password_hash,
        role='citizen',
        full_name=full_name,
        phone=phone,
        area=area,
    )

    flash("Account created successfully! Please log in.", "success")
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))
