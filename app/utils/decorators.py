from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user, login_required


def role_required(*roles):
    """
    Decorator to require specific role(s) for access.
    Also enforces temp password check - redirects to change_password if needed.

    Usage:
        @role_required('admin')
        @role_required('admin', 'salesperson')
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            # Check temp password first
            if current_user.is_temp_password:
                flash('You must change your temporary password before continuing.', 'info')
                return redirect(url_for('auth.change_password'))

            # Check role
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('auth.dashboard_redirect'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Shortcut decorator for admin-only routes."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_temp_password:
            flash('You must change your temporary password before continuing.', 'info')
            return redirect(url_for('auth.change_password'))

        if current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.dashboard_redirect'))

        return f(*args, **kwargs)
    return decorated_function


def salesperson_required(f):
    """Shortcut decorator for salesperson routes. Also allows admins."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_temp_password:
            flash('You must change your temporary password before continuing.', 'info')
            return redirect(url_for('auth.change_password'))

        # Allow both salesperson and admin roles
        if current_user.role not in ('salesperson', 'admin'):
            flash('Salesperson access required.', 'error')
            return redirect(url_for('auth.dashboard_redirect'))

        return f(*args, **kwargs)
    return decorated_function


def temp_password_check(f):
    """
    Decorator to enforce temp password check without role restriction.
    Redirects to change_password if user has a temporary password.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_temp_password:
            flash('You must change your temporary password before continuing.', 'info')
            return redirect(url_for('auth.change_password'))
        return f(*args, **kwargs)
    return decorated_function


def gemach_required(f):
    """Decorator for Gemach (charitable fund) routes.
    Allows users with role 'admin' or 'gemach_user'.
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.is_temp_password:
            flash('You must change your temporary password before continuing.', 'info')
            return redirect(url_for('auth.change_password'))

        if current_user.role not in ('admin', 'gemach_user'):
            flash('Gemach access required.', 'error')
            return redirect(url_for('auth.dashboard_redirect'))

        return f(*args, **kwargs)
    return decorated_function
