import os
import logging
from datetime import datetime
from flask import request, render_template_string, flash, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from . import upload_bp
from ...extensions import csrf

logger = logging.getLogger(__name__)

# Upload configuration
UPLOAD_FOLDER = '/var/www/matat/uploads'
UPLOAD_TOKEN = 'matat2026'  # Simple access token
ALLOWED_EXTENSIONS = {
    'accdb', 'mdb',  # Access databases
    'xls', 'xlsx', 'csv',  # Spreadsheets
    'sql', 'bak',  # Database exports
    'zip', 'rar', '7z',  # Archives
    'pdf', 'doc', 'docx', 'txt',  # Documents
    'py', 'js', 'json', 'xml'  # Code/config
}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


UPLOAD_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>File Upload - Matat Migration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 {
            margin: 0 0 10px 0;
            color: #2c3e50;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #333;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 16px;
        }
        input[type="file"] {
            width: 100%;
            padding: 12px;
            border: 2px dashed #ddd;
            border-radius: 6px;
            background: #f9f9f9;
            cursor: pointer;
        }
        input[type="file"]:hover {
            border-color: #3498db;
        }
        button {
            width: 100%;
            padding: 14px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
        }
        button:hover {
            background: #2980b9;
        }
        .flash {
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .flash.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .flash.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .allowed-types {
            font-size: 12px;
            color: #888;
            margin-top: 8px;
        }
        .files-list {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .files-list h3 {
            margin: 0 0 15px 0;
            color: #333;
        }
        .file-item {
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .file-name {
            font-family: monospace;
            color: #2c3e50;
        }
        .file-size {
            color: #888;
            font-size: 12px;
        }
        .upload-progress {
            display: none;
            margin-top: 15px;
        }
        .progress-bar {
            height: 20px;
            background: #eee;
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: #3498db;
            width: 0%;
            transition: width 0.3s;
        }
        .progress-text {
            text-align: center;
            margin-top: 8px;
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>File Upload</h1>
        <p class="subtitle">Upload Access databases and other files for migration</p>

        {% for category, message in messages %}
        <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}

        <form method="POST" enctype="multipart/form-data" id="uploadForm">
            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

            <div class="form-group">
                <label for="token">Access Token</label>
                <input type="password" id="token" name="token" required placeholder="Enter the access token">
            </div>

            <div class="form-group">
                <label for="description">Description (optional)</label>
                <input type="text" id="description" name="description" placeholder="What is this file?">
            </div>

            <div class="form-group">
                <label for="file">Select File</label>
                <input type="file" id="file" name="file" required>
                <p class="allowed-types">Allowed: .accdb, .mdb, .xlsx, .csv, .sql, .zip, .pdf, .py, etc. (max 500MB)</p>
            </div>

            <button type="submit">Upload File</button>

            <div class="upload-progress" id="progress">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-text" id="progressText">Uploading...</div>
            </div>
        </form>

        {% if files %}
        <div class="files-list">
            <h3>Uploaded Files</h3>
            {% for file in files %}
            <div class="file-item">
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ file.size }}</span>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', function() {
            document.getElementById('progress').style.display = 'block';
        });
    </script>
</body>
</html>
'''


@upload_bp.route('/', methods=['GET', 'POST'])
@csrf.exempt
def upload_file():
    """Public file upload page."""
    messages = []

    if request.method == 'POST':
        token = request.form.get('token', '')

        if token != UPLOAD_TOKEN:
            messages.append(('error', 'Invalid access token.'))
        elif 'file' not in request.files:
            messages.append(('error', 'No file selected.'))
        else:
            file = request.files['file']

            if file.filename == '':
                messages.append(('error', 'No file selected.'))
            elif not allowed_file(file.filename):
                messages.append(('error', f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'))
            else:
                # Create timestamped filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                original_name = secure_filename(file.filename)
                filename = f'{timestamp}_{original_name}'
                filepath = os.path.join(UPLOAD_FOLDER, filename)

                # Save file
                file.save(filepath)

                # Log upload
                description = request.form.get('description', '')
                file_size = os.path.getsize(filepath)
                logger.info(f'[upload] File uploaded: {filename} ({file_size} bytes) - {description}')

                # Save metadata
                with open(os.path.join(UPLOAD_FOLDER, 'uploads.log'), 'a') as f:
                    f.write(f'{datetime.now().isoformat()} | {filename} | {file_size} | {description}\n')

                messages.append(('success', f'File "{original_name}" uploaded successfully!'))

    # List existing files
    files = []
    if os.path.exists(UPLOAD_FOLDER):
        for f in sorted(os.listdir(UPLOAD_FOLDER), reverse=True):
            if f != 'uploads.log':
                filepath = os.path.join(UPLOAD_FOLDER, f)
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    if size > 1024 * 1024:
                        size_str = f'{size / (1024*1024):.1f} MB'
                    elif size > 1024:
                        size_str = f'{size / 1024:.1f} KB'
                    else:
                        size_str = f'{size} bytes'
                    files.append({'name': f, 'size': size_str})

    from flask import render_template_string
    from flask_wtf.csrf import generate_csrf
    return render_template_string(
        UPLOAD_PAGE,
        messages=messages,
        files=files[:10],  # Show last 10 files
        csrf_token=generate_csrf()
    )
