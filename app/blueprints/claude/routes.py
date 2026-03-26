import os
import uuid
import logging
import subprocess
from datetime import datetime
from flask import request, render_template, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from . import claude_bp
from ...extensions import db, csrf
from ...models.claude_session import ClaudeSession, ClaudeScreenshot, ClaudeConfig

logger = logging.getLogger(__name__)

# Configuration
SCREENSHOT_FOLDER = '/root/matat/uploads/screenshots'
TTYD_PORT = 7681
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

# Ensure screenshot folder exists
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)


def get_tmux_session():
    """Get current tmux session from config or default."""
    return ClaudeConfig.get('tmux_session', '4')


def is_ttyd_running():
    """Check if ttyd-matat service is running."""
    try:
        result = subprocess.run(
            ['/usr/bin/systemctl', 'is-active', 'ttyd-matat'],
            capture_output=True, text=True
        )
        return result.stdout.strip() == 'active'
    except Exception as e:
        logger.error(f'[claude] Failed to check ttyd status: {e}')
        return False


def start_ttyd():
    """Start ttyd-matat service."""
    if is_ttyd_running():
        return True

    try:
        subprocess.run(['/usr/bin/systemctl', 'start', 'ttyd-matat'], capture_output=True)
        logger.info(f'[claude] Started ttyd-matat service')
        return True
    except Exception as e:
        logger.error(f'[claude] Failed to start ttyd-matat: {e}')
        return False


@claude_bp.route('/')
@login_required
def chat():
    """Main Claude chat interface with embedded terminal."""
    # Get or create active session
    active_session = ClaudeSession.query.filter(
        ClaudeSession.user_id == current_user.id,
        ClaudeSession.ended_at.is_(None)
    ).first()

    if not active_session:
        # Create new session
        active_session = ClaudeSession(
            user_id=current_user.id,
            tmux_session=get_tmux_session()
        )
        db.session.add(active_session)
        db.session.commit()
        logger.info(f'[claude] New session {active_session.id} started by user {current_user.id}')

    # Ensure ttyd is running
    start_ttyd()

    # Get recent sessions for this user
    recent_sessions = ClaudeSession.query.filter(
        ClaudeSession.user_id == current_user.id
    ).order_by(ClaudeSession.started_at.desc()).limit(10).all()

    # Get screenshots for current session
    screenshots = ClaudeScreenshot.query.filter(
        ClaudeScreenshot.session_id == active_session.id
    ).order_by(ClaudeScreenshot.created_at.desc()).all()

    return render_template(
        'claude/chat.html',
        session=active_session,
        recent_sessions=recent_sessions,
        screenshots=screenshots,
        ttyd_port=TTYD_PORT,
        tmux_session=get_tmux_session()
    )


@claude_bp.route('/session/start', methods=['POST'])
@login_required
def start_session():
    """Start a new Claude session."""
    # End any existing active session
    active_session = ClaudeSession.query.filter(
        ClaudeSession.user_id == current_user.id,
        ClaudeSession.ended_at.is_(None)
    ).first()

    if active_session:
        active_session.ended_at = datetime.utcnow()

    # Create new session
    purpose = request.form.get('purpose', '')
    new_session = ClaudeSession(
        user_id=current_user.id,
        tmux_session=get_tmux_session(),
        purpose=purpose
    )
    db.session.add(new_session)
    db.session.commit()

    logger.info(f'[claude] Session {new_session.id} started by user {current_user.id}: {purpose}')
    flash('New session started.', 'success')
    return redirect(url_for('claude.chat'))


@claude_bp.route('/session/end', methods=['POST'])
@login_required
def end_session():
    """End the current Claude session."""
    active_session = ClaudeSession.query.filter(
        ClaudeSession.user_id == current_user.id,
        ClaudeSession.ended_at.is_(None)
    ).first()

    if active_session:
        active_session.ended_at = datetime.utcnow()
        active_session.notes = request.form.get('notes', '')
        db.session.commit()
        logger.info(f'[claude] Session {active_session.id} ended by user {current_user.id}')
        flash('Session ended.', 'success')
    else:
        flash('No active session to end.', 'error')

    return redirect(url_for('claude.chat'))


@claude_bp.route('/session/<int:id>')
@login_required
def view_session(id):
    """View a past session."""
    session = ClaudeSession.query.get_or_404(id)

    # Only allow viewing own sessions (unless admin)
    if session.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('claude.chat'))

    screenshots = ClaudeScreenshot.query.filter(
        ClaudeScreenshot.session_id == id
    ).order_by(ClaudeScreenshot.created_at.desc()).all()

    return render_template(
        'claude/session_detail.html',
        session=session,
        screenshots=screenshots
    )


@claude_bp.route('/screenshot/upload', methods=['POST'])
@login_required
@csrf.exempt
def upload_screenshot():
    """Upload a screenshot (via paste or file upload)."""
    active_session = ClaudeSession.query.filter(
        ClaudeSession.user_id == current_user.id,
        ClaudeSession.ended_at.is_(None)
    ).first()

    if 'file' not in request.files and 'image' not in request.form:
        return jsonify({'error': 'No image provided'}), 400

    try:
        # Handle base64 pasted image
        if 'image' in request.form:
            import base64
            image_data = request.form['image']
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]

            image_bytes = base64.b64decode(image_data)
            filename = f'{uuid.uuid4().hex}.png'
            filepath = os.path.join(SCREENSHOT_FOLDER, filename)

            with open(filepath, 'wb') as f:
                f.write(image_bytes)

            file_size = len(image_bytes)
            original_filename = 'pasted_image.png'

        # Handle file upload
        else:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                return jsonify({'error': 'Invalid image type'}), 400

            filename = f'{uuid.uuid4().hex}.{ext}'
            filepath = os.path.join(SCREENSHOT_FOLDER, filename)
            file.save(filepath)

            file_size = os.path.getsize(filepath)
            original_filename = secure_filename(file.filename)

        # Create database record
        screenshot = ClaudeScreenshot(
            session_id=active_session.id if active_session else None,
            user_id=current_user.id,
            filename=filename,
            original_filename=original_filename,
            file_path=filepath,
            file_size=file_size,
            description=request.form.get('description', '')
        )
        db.session.add(screenshot)
        db.session.commit()

        logger.info(f'[claude] Screenshot {filename} uploaded by user {current_user.id}')

        return jsonify({
            'success': True,
            'url': screenshot.url,
            'filename': filename,
            'id': screenshot.id
        })

    except Exception as e:
        logger.error(f'[claude] Screenshot upload failed: {e}')
        return jsonify({'error': str(e)}), 500


@claude_bp.route('/screenshot/<filename>')
def view_screenshot(filename):
    """Serve a screenshot image."""
    # Sanitize filename
    filename = secure_filename(filename)
    filepath = os.path.join(SCREENSHOT_FOLDER, filename)

    if not os.path.exists(filepath):
        return 'Not found', 404

    return send_file(filepath)


@claude_bp.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    """Configure Claude integration (admin only)."""
    if current_user.role != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('claude.chat'))

    if request.method == 'POST':
        tmux_session = request.form.get('tmux_session', '4')
        ClaudeConfig.set('tmux_session', tmux_session)
        flash('Configuration updated.', 'success')
        logger.info(f'[claude] Config updated: tmux_session={tmux_session}')
        return redirect(url_for('claude.config'))

    return render_template(
        'claude/config.html',
        tmux_session=get_tmux_session(),
        ttyd_running=is_ttyd_running()
    )


@claude_bp.route('/ttyd/restart', methods=['POST'])
@login_required
def restart_ttyd():
    """Restart ttyd (admin only)."""
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    try:
        # Restart ttyd-matat service
        subprocess.run(['/usr/bin/systemctl', 'restart', 'ttyd-matat'], capture_output=True)
        import time
        time.sleep(2)
        return jsonify({'success': True, 'running': is_ttyd_running()})
    except Exception as e:
        logger.error(f'[claude] Failed to restart ttyd: {e}')
        return jsonify({'error': str(e)}), 500


@claude_bp.route('/sessions')
@login_required
def list_sessions():
    """List all Claude sessions (admin sees all, users see own)."""
    if current_user.role == 'admin':
        sessions = ClaudeSession.query.order_by(ClaudeSession.started_at.desc()).limit(50).all()
    else:
        sessions = ClaudeSession.query.filter(
            ClaudeSession.user_id == current_user.id
        ).order_by(ClaudeSession.started_at.desc()).limit(50).all()

    return render_template('claude/sessions.html', sessions=sessions)
