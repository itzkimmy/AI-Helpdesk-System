"""
Beyond2U AI-Powered IT Helpdesk - Application Configuration

Environment-based configuration with Dev, Test, and Production profiles.
Secrets are loaded from environment variables only.
"""

import os
from datetime import timedelta


class BaseConfig:
    """Shared configuration for all environments."""

    # --- Flask core ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'CHANGE-ME-generate-a-real-secret-key')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # --- Database ---
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }

    # --- Session ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', 30))
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=0)

    # --- CSRF ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # --- SLA ---
    SLA_WARNING_THRESHOLD_PCT = int(os.environ.get('SLA_WARNING_THRESHOLD_PCT', 75))
    SLA_SCAN_INTERVAL_SECONDS = int(os.environ.get('SLA_SCAN_INTERVAL_SECONDS', 60))

    # --- Security ---
    TRUSTED_HOSTS = [
        h.strip() for h in os.environ.get('TRUSTED_HOSTS', '').split(',') if h.strip()
    ]
    LOGIN_MAX_ATTEMPTS = int(os.environ.get('LOGIN_MAX_ATTEMPTS', 5))
    LOGIN_LOCKOUT_SECONDS = int(os.environ.get('LOGIN_LOCKOUT_SECONDS', 900))

    # --- Timezone ---
    DISPLAY_TIMEZONE = os.environ.get('DISPLAY_TIMEZONE', 'Asia/Kuala_Lumpur')

    # --- ML ---
    ML_MODEL_DIR = os.environ.get('ML_MODEL_DIR', 'app/ml/models')

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_DEFAULT = '200/hour'


class DevelopmentConfig(BaseConfig):
    """Development environment configuration."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'helpdesk_dev.db'))}"
    )
    SESSION_COOKIE_SECURE = False

    # More permissive rate limits for development
    RATELIMIT_DEFAULT = '1000/hour'


class TestingConfig(BaseConfig):
    """Testing environment configuration."""

    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///:memory:'
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False  # Disable CSRF in tests for convenience
    LOGIN_DISABLED = False

    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False

    # Use in-memory for speed
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ProductionConfig(BaseConfig):
    """Production environment configuration."""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'helpdesk.db'))}"
    )
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SECRET_KEY = os.environ.get('SECRET_KEY') or BaseConfig.SECRET_KEY


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
