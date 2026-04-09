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
from ...models.help_request import HelpRequest
from ...models.chat_message import ChatMessage
from ...models.chat_archive import ChatArchive
from ...models.config_settings import ConfigSettings

logger = logging.getLogger(__name__)

# Anthropic API key - set this in environment or database
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# Configuration
SCREENSHOT_FOLDER = '/var/www/matat/uploads/screenshots'
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


@claude_bp.route('/help/submit', methods=['POST'])
@login_required
@csrf.exempt
def submit_help_request():
    """Submit a help request."""
    try:
        issue = request.form.get('issue', '').strip()
        page_url = request.form.get('page_url', '')
        screenshot_id = request.form.get('screenshot_id')

        if not issue:
            return jsonify({'error': 'Please describe your issue'}), 400

        help_req = HelpRequest(
            user_id=current_user.id,
            page_url=page_url,
            issue=issue,
            screenshot_id=int(screenshot_id) if screenshot_id else None
        )
        db.session.add(help_req)
        db.session.commit()

        logger.info(f'[claude] Help request {help_req.id} submitted by {current_user.full_name}')

        return jsonify({
            'success': True,
            'message': 'Your request has been submitted! We will look into it.',
            'id': help_req.id
        })

    except Exception as e:
        logger.error(f'[claude] Help request submission failed: {e}')
        return jsonify({'error': str(e)}), 500


@claude_bp.route('/help/requests')
@login_required
def list_help_requests():
    """List help requests (admin sees all, users see own)."""
    if current_user.role == 'admin':
        requests = HelpRequest.query.order_by(HelpRequest.created_at.desc()).all()
    else:
        requests = HelpRequest.query.filter(
            HelpRequest.user_id == current_user.id
        ).order_by(HelpRequest.created_at.desc()).all()

    return render_template('claude/help_requests.html', requests=requests)


@claude_bp.route('/help/request/<int:id>')
@login_required
def view_help_request(id):
    """View a help request."""
    help_req = HelpRequest.query.get_or_404(id)

    # Only allow viewing own requests (unless admin)
    if help_req.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('claude.list_help_requests'))

    return render_template('claude/help_request_detail.html', request=help_req)


@claude_bp.route('/help/request/<int:id>/resolve', methods=['POST'])
@login_required
def resolve_help_request(id):
    """Resolve a help request (admin only)."""
    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    help_req = HelpRequest.query.get_or_404(id)
    help_req.status = request.form.get('status', 'resolved')
    help_req.resolution = request.form.get('resolution', '')
    help_req.referred_to = request.form.get('referred_to', '')
    help_req.resolved_at = datetime.utcnow()
    db.session.commit()

    logger.info(f'[claude] Help request {id} resolved: {help_req.status}')
    return jsonify({'success': True})


@claude_bp.route('/chat/send', methods=['POST'])
@login_required
@csrf.exempt
def chat_send():
    """Send a message to Claude and get a response."""
    import anthropic

    message = request.form.get('message', '').strip()
    page_url = request.form.get('page_url', '')
    screenshot_id = request.form.get('screenshot_id')

    if not message:
        return jsonify({'error': 'Please enter a message'}), 400

    # Get API key from environment or database
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        config = ConfigSettings.query.first()
        api_key = config.anthropic_api_key if config else None
    if not api_key:
        return jsonify({'error': 'Chat not configured. Please contact the administrator.'}), 500

    try:
        # Save user message
        user_msg = ChatMessage(
            user_id=current_user.id,
            role='user',
            content=message,
            page_url=page_url,
            screenshot_id=int(screenshot_id) if screenshot_id else None
        )
        db.session.add(user_msg)
        db.session.commit()

        # Get recent chat history for context (last 10 messages)
        recent_messages = ChatMessage.query.filter_by(
            user_id=current_user.id
        ).order_by(ChatMessage.created_at.desc()).limit(10).all()
        recent_messages.reverse()  # Oldest first

        # Build conversation history
        conversation = []
        for msg in recent_messages:
            conversation.append({
                'role': msg.role,
                'content': msg.content
            })

        # Build system prompt with user context
        user_notes = current_user.claude_notes or ''
        system_prompt = f"""You are a helpful assistant for the Matat Mordechai donation management system.
You help users with questions about using the system, finding features, and resolving issues.

USER CONTEXT:
{user_notes}

CURRENT PAGE: {page_url}

GUIDELINES:
- Be friendly, patient, and helpful
- Use simple, clear language
- If the user needs a fix or has a bug, help them if you can explain how to work around it
- For new feature requests or development work, let them know you'll pass it to Menachem Kantor (the developer)
- Keep responses concise but complete
- If you don't know something about the system, say so honestly"""

        # Call Claude API
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=conversation
        )

        assistant_content = response.content[0].text

        # Save assistant response
        assistant_msg = ChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=assistant_content
        )
        db.session.add(assistant_msg)
        db.session.commit()

        logger.info(f'[claude] Chat message from {current_user.full_name}: {message[:50]}...')

        return jsonify({
            'success': True,
            'response': assistant_content,
            'message_id': assistant_msg.id
        })

    except anthropic.APIError as e:
        logger.error(f'[claude] Anthropic API error: {e}')
        return jsonify({'error': 'Sorry, I had trouble responding. Please try again.'}), 500
    except Exception as e:
        logger.error(f'[claude] Chat error: {e}')
        return jsonify({'error': str(e)}), 500


@claude_bp.route('/chat/history')
@login_required
def chat_history():
    """Get chat history for current user."""
    messages = ChatMessage.query.filter_by(
        user_id=current_user.id
    ).order_by(ChatMessage.created_at.desc()).limit(50).all()
    messages.reverse()  # Oldest first

    return jsonify({
        'messages': [msg.to_dict() for msg in messages]
    })


@claude_bp.route('/chat/clear', methods=['POST'])
@login_required
@csrf.exempt
def chat_clear():
    """Clear chat history for current user (archives first)."""
    import json

    # Get messages to archive
    messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_at).all()

    if messages:
        # Archive the conversation
        messages_data = [{
            'role': m.role,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
            'page_url': m.page_url
        } for m in messages]

        archive = ChatArchive(
            user_id=current_user.id,
            messages_json=json.dumps(messages_data),
            message_count=len(messages),
            archived_by=current_user.id
        )
        db.session.add(archive)

        # Now delete the messages
        ChatMessage.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

    return jsonify({'success': True})


@claude_bp.route('/chat/admin')
@login_required
def chat_admin():
    """View all user chat conversations (admin only)."""
    if current_user.role != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('claude.chat'))

    from ...models import User
    from sqlalchemy import func

    # Get all users with chat messages
    users_with_chats = db.session.query(
        ChatMessage.user_id,
        func.max(ChatMessage.created_at).label('last_message'),
        func.count(ChatMessage.id).label('message_count')
    ).group_by(ChatMessage.user_id).all()

    conversations = {}
    for user_id, last_message, count in users_with_chats:
        user = User.query.get(user_id)
        if not user or user.username == 'admin':
            continue

        messages = ChatMessage.query.filter_by(user_id=user_id).order_by(ChatMessage.created_at).all()

        # Check if user mentioned needing developer/Menachem
        needs_attention = any(
            'menachem' in m.content.lower() or
            'developer' in m.content.lower() or
            'new feature' in m.content.lower()
            for m in messages if m.role == 'assistant'
        )

        conversations[user_id] = {
            'user': user,
            'messages': messages,
            'last_message': last_message,
            'needs_attention': needs_attention
        }

    # Sort by needs_attention first, then by last_message
    conversations = dict(sorted(
        conversations.items(),
        key=lambda x: (not x[1]['needs_attention'], x[1]['last_message']),
        reverse=True
    ))

    return render_template('claude/chat_admin.html', conversations=conversations)


@claude_bp.route('/chat/clear/<int:user_id>', methods=['POST'])
@login_required
@csrf.exempt
def chat_clear_user(user_id):
    """Clear chat history for a specific user (admin only, archives first)."""
    import json

    if current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    # Get messages to archive
    messages = ChatMessage.query.filter_by(user_id=user_id).order_by(ChatMessage.created_at).all()

    if messages:
        # Archive the conversation
        messages_data = [{
            'role': m.role,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
            'page_url': m.page_url
        } for m in messages]

        resolution = request.form.get('resolution', '')

        archive = ChatArchive(
            user_id=user_id,
            messages_json=json.dumps(messages_data),
            message_count=len(messages),
            resolution_notes=resolution,
            archived_by=current_user.id
        )
        db.session.add(archive)

        # Now delete
        ChatMessage.query.filter_by(user_id=user_id).delete()
        db.session.commit()

    return jsonify({'success': True})


@claude_bp.route('/chat/archives')
@login_required
def chat_archives():
    """View archived chat conversations (admin only)."""
    if current_user.role != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('claude.chat'))

    archives = ChatArchive.query.order_by(ChatArchive.archived_at.desc()).all()
    return render_template('claude/chat_archives.html', archives=archives)


@claude_bp.route('/chat/archive/<int:id>')
@login_required
def view_archive(id):
    """View a specific archived conversation."""
    import json

    if current_user.role != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('claude.chat'))

    archive = ChatArchive.query.get_or_404(id)
    messages = json.loads(archive.messages_json)

    return render_template('claude/chat_archive_detail.html', archive=archive, messages=messages)
