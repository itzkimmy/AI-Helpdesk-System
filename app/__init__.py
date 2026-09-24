"""
Beyond2U AI-Powered IT Helpdesk - Application Factory

Creates and configures the Flask application with blueprints, extensions,
security headers, error handlers, and template context processors.
"""

import os
import time
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request, g
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name=None):
    """Application factory. Creates and returns a fully configured Flask app."""

    app = Flask(__name__)

    # Load configuration
    config_name = config_name or os.environ.get('FLASK_CONFIG', 'development')
    app.config.from_object(config_by_name[config_name])
    import uuid

    # Unique identifier for this running server instance
    app.config['SERVER_INSTANCE_ID'] = uuid.uuid4().hex

    # Initialise extensions
    _init_extensions(app)

    # Register session security (invalidates logins on server restart)
    _register_session_security(app)

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register security headers
    _register_security_headers(app)

    # Register template context processors
    _register_context_processors(app)

    # Register CLI commands
    _register_cli_commands(app)

    # Configure logging
    _configure_logging(app)

    # Trusted host validation
    _register_trusted_hosts(app)

    # Auto-run SLA scan on each request (throttled)
    _register_sla_autoscan(app)

    return app


def _init_extensions(app):
    """Initialise Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    if app.config.get('RATELIMIT_ENABLED', True):
        limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return db.session.get(User, int(user_id))


def _register_blueprints(app):
    """Register all application blueprints."""
    from app.blueprints.auth import auth_bp
    from app.blueprints.client import client_bp
    from app.blueprints.technician import technician_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.main import main_bp
    from app.blueprints.kb import kb_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(kb_bp, url_prefix='/kb')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(technician_bp, url_prefix='/technician')
    app.register_blueprint(admin_bp, url_prefix='/admin')


def _register_error_handlers(app):
    """Register custom error pages."""

    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error('Unhandled 500 error: %s', e, exc_info=True)
        db.session.rollback()
        return render_template('errors/500.html'), 500


def _register_security_headers(app):
    """Add security headers to every response."""

    @app.after_request
    def set_security_headers(response):
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers['Content-Security-Policy'] = csp
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=()'
        )

        # HSTS only in production
        if not app.debug:
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )

        return response


def _register_context_processors(app):
    """Add shared template context variables."""

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        display_tz = app.config.get('DISPLAY_TIMEZONE', 'Asia/Kuala_Lumpur')
        try:
            tz = ZoneInfo(display_tz)
        except Exception:
            tz = timezone.utc

        def to_local_time(utc_dt):
            """Convert UTC datetime to display timezone."""
            if utc_dt is None:
                return None
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            return utc_dt.astimezone(tz)

        # Unread notification count — only meaningful for admins
        unread_count = 0
        try:
            if current_user.is_authenticated and current_user.is_admin:
                from app.services.notifications import NotificationService
                unread_count = NotificationService.unread_count_for(current_user)
        except Exception:
            pass

        return {
            'now_utc': datetime.now(timezone.utc),
            'to_local_time': to_local_time,
            'display_timezone': display_tz,
            'unread_notification_count': unread_count,
        }


def _register_cli_commands(app):
    """Register custom Flask CLI commands."""

    @app.cli.command('seed')
    def seed_command():
        """Seed the database with demo data."""
        from scripts.seed import run_seed
        run_seed(app)

    @app.cli.command('train-models')
    def train_models_command():
        """Train ML classification models."""
        from scripts.train_models import run_training
        run_training()

    @app.cli.command('verify-audit')
    def verify_audit_command():
        """Verify the integrity of all ticket audit chains."""
        from scripts.verify_audit import run_verification
        run_verification(app)


def _configure_logging(app):
    """Configure structured logging without sensitive data."""
    if not app.debug:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)


def _register_trusted_hosts(app):
    """Validate the Host header against configured trusted hosts."""
    trusted = app.config.get('TRUSTED_HOSTS', [])
    if trusted:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)

        @app.before_request
        def check_host():
            host = request.host.split(':')[0]
            if host not in trusted and host != 'localhost' and host != '127.0.0.1':
                from flask import abort
                abort(400, 'Invalid host header')


# Module-level timestamp so the throttle survives across requests.
_last_sla_scan: float = 0.0


def _register_sla_autoscan(app):
    """Run SLA scan automatically on web requests, at most once every 60 s.

    This means the separate ``scheduler.py`` process is optional — SLA states
    will still be refreshed as long as someone is browsing the application.
    """
    global _last_sla_scan
    scan_interval = int(os.environ.get('SLA_SCAN_INTERVAL_SECONDS', 60))

    @app.before_request
    def auto_sla_scan():
        global _last_sla_scan
        # Only scan for non-static requests
        if request.endpoint == 'static':
            return
        now = time.monotonic()
        if now - _last_sla_scan >= scan_interval:
            _last_sla_scan = now
            try:
                from app.services.sla import SLAService
                SLAService.scan_and_update()
            except Exception as exc:  # pragma: no cover
                app.logger.error('Auto SLA scan error: %s', exc)


def _register_session_security(app):
    """Ensure active sessions are automatically invalidated upon server restart or session timeout."""
    @app.before_request
    def validate_session_instance():
        # Skip static assets
        if request.endpoint == 'static':
            return

        from flask import session
        from flask_login import current_user, logout_user

        if current_user.is_authenticated:
            server_id = app.config.get('SERVER_INSTANCE_ID')
            session_server_id = session.get('_server_instance_id')
            if not session_server_id or session_server_id != server_id:
                logout_user()
                session.clear()

