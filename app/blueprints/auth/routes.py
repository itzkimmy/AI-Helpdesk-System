"""
Authentication routes — login, registration, logout.

Security measures:
- Generic error messages (no user enumeration)
- Login throttling via failed_login_attempts + lockout
- Session rotation after authentication
- CSRF protection (inherited from Flask-WTF)
- No destructive GET requests
"""

import logging
from datetime import datetime, timedelta, timezone

from flask import (
    render_template, redirect, url_for, flash, request, session, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user

from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import LoginForm
from app.extensions import db, limiter
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# Generic login error to prevent user enumeration
_LOGIN_ERROR = 'Invalid email or password. Please try again.'


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10/minute', methods=['POST'])
def login():
    """Sign in with email and password."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        if user is None:
            flash(_LOGIN_ERROR, 'danger')
            logger.info('Login attempt for non-existent email')
            return render_template('auth/login.html', form=form)

        # Check account lock
        if user.is_account_locked():
            flash(
                'Account temporarily locked due to too many failed attempts. '
                'Please try again later.',
                'danger',
            )
            logger.info('Login attempt on locked account user_id=%d', user.id)
            return render_template('auth/login.html', form=form)

        # Check active status
        if not user.is_active:
            flash(_LOGIN_ERROR, 'danger')
            logger.info('Login attempt on deactivated account user_id=%d', user.id)
            return render_template('auth/login.html', form=form)

        # Verify password
        if not user.check_password(form.password.data):
            _record_failed_login(user)
            flash(_LOGIN_ERROR, 'danger')
            logger.info('Failed login attempt user_id=%d', user.id)
            return render_template('auth/login.html', form=form)

        # Successful login — reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()

        # Rehash if needed (parameter upgrade)
        if user.needs_rehash():
            user.set_password(form.password.data)
            db.session.commit()

        # Session rotation: clear old session data before login
        session.clear()

        # Bind session to the current server instance for automatic invalidation on restart
        session['_server_instance_id'] = current_app.config.get('SERVER_INSTANCE_ID')

        login_user(user, remember=False)
        session.permanent = False

        logger.info('Successful login user_id=%d role=%s', user.id, user.role.value)

        # Safe redirect — only allow relative URLs
        next_page = request.args.get('next', '')
        if next_page and _is_safe_redirect(next_page):
            return redirect(next_page)
        return _redirect_by_role(user)

    return render_template('auth/login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Public self-registration is disabled. Only administrators can create accounts."""
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    flash('Public account registration is disabled. Please contact your IT administrator to request an account.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Sign out — POST only to prevent CSRF via GET."""
    user_id = current_user.id
    logout_user()
    session.clear()
    logger.info('Logout user_id=%d', user_id)
    return redirect(url_for('auth.login'))


def _record_failed_login(user):
    """Increment failed login counter and lock if threshold reached."""
    max_attempts = current_app.config.get('LOGIN_MAX_ATTEMPTS', 5)
    lockout_seconds = current_app.config.get('LOGIN_LOCKOUT_SECONDS', 900)

    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= max_attempts:
        user.locked_until = datetime.now(timezone.utc) + timedelta(seconds=lockout_seconds)
        logger.warning(
            'Account locked user_id=%d after %d failed attempts',
            user.id, user.failed_login_attempts,
        )
    db.session.commit()


def _redirect_by_role(user):
    """Redirect user to their role-specific dashboard."""
    if user.is_admin:
        return redirect(url_for('admin.dashboard'))
    elif user.is_technician:
        return redirect(url_for('technician.dashboard'))
    return redirect(url_for('client.dashboard'))


def _is_safe_redirect(target):
    """Validate redirect target is a relative URL (no open redirect)."""
    if not target:
        return False
    # Only allow relative paths starting with /
    if target.startswith('//') or target.startswith('http'):
        return False
    return target.startswith('/')
