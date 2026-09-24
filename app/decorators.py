"""
RBAC and access-control decorators.

Provides role-checking decorators for route-level access control.
Object-level authorisation is enforced in services.
"""

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required


def role_required(*roles):
    """
    Decorator that restricts access to users with specific roles.
    
    Usage:
        @role_required(UserRole.ADMIN)
        def admin_view(): ...
        
        @role_required(UserRole.ADMIN, UserRole.TECHNICIAN)
        def staff_view(): ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            if not current_user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Shortcut decorator for admin-only routes."""
    from app.models.user import UserRole
    return role_required(UserRole.ADMIN)(f)


def technician_required(f):
    """Shortcut decorator for technician-only routes."""
    from app.models.user import UserRole
    return role_required(UserRole.TECHNICIAN)(f)


def client_required(f):
    """Shortcut decorator for client-only routes."""
    from app.models.user import UserRole
    return role_required(UserRole.CLIENT)(f)


def staff_required(f):
    """Decorator for routes accessible to technicians AND admins."""
    from app.models.user import UserRole
    return role_required(UserRole.TECHNICIAN, UserRole.ADMIN)(f)
