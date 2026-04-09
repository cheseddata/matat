from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from ...extensions import db, bcrypt
from ...models.user import User


@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard_redirect'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.active and not user.is_deleted:
            if bcrypt.check_password_hash(user.password_hash, password):
                login_user(user)
                if user.is_temp_password:
                    return redirect(url_for('auth.change_password'))
                return redirect(url_for('auth.dashboard_redirect'))
        
        flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or len(new_password) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif new_password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            current_user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
            current_user.is_temp_password = False
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('auth.dashboard_redirect'))
    
    return render_template('auth/change_password.html')


@auth_bp.route('/dashboard-redirect')
@login_required
def dashboard_redirect():
    if current_user.is_temp_password:
        return redirect(url_for('auth.change_password'))
    
    if current_user.role == 'admin':
        return redirect(url_for('admin.donations'))
    else:
        return redirect(url_for('salesperson.dashboard'))
