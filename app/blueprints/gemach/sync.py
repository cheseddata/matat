"""Gemach Access-sync route — kicks off sync_live_data.bat in a background
thread, streams progress into module-level state, persists each run to
`instance/sync_logs/`, and exposes polling + history endpoints."""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
from datetime import datetime

from flask import abort, jsonify, render_template, send_file

from ...extensions import csrf
from ...utils.decorators import gemach_required
from . import gemach_bp

logger = logging.getLogger(__name__)

# Repo root is four levels up from this file (app/blueprints/gemach/sync.py)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SYNC_BAT = os.path.join(REPO_ROOT, 'sync_live_data.bat')
SYNC_LOGS_DIR = os.path.join(REPO_ROOT, 'instance', 'sync_logs')
os.makedirs(SYNC_LOGS_DIR, exist_ok=True)

_state = {
    'running': False,
    'started_at': None,
    'finished_at': None,
    'returncode': None,
    'output': '',
    'error': None,
}
_lock = threading.Lock()


def _log_path_for(started_at: str, ok: bool | None) -> str:
    ts_safe = re.sub(r'[^0-9T]', '', (started_at or ''))[:15] or datetime.now().strftime('%Y%m%dT%H%M%S')
    suffix = 'ok' if ok is True else ('fail' if ok is False else 'running')
    return os.path.join(SYNC_LOGS_DIR, f'{ts_safe}_{suffix}.log')


def _write_log_header(path: str, started_at, finished_at, returncode, error):
    """Rewrite header + preserve existing body when transitioning states."""
    try:
        body = ''
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                existing = f.read()
            if '# ----------------------------------------\n' in existing:
                body = existing.split('# ----------------------------------------\n', 1)[1]
        with open(path, 'w', encoding='utf-8', errors='replace') as f:
            f.write('# sync_live_data.bat run\n')
            f.write(f'# started:  {started_at}\n')
            f.write(f'# finished: {finished_at or ""}\n')
            f.write(f'# returncode: {returncode if returncode is not None else ""}\n')
            f.write(f'# error: {error or ""}\n')
            f.write('# ----------------------------------------\n')
            f.write(body)
    except Exception:
        logger.exception('[gemach.sync] failed to write log header')


def _parse_log_header(path: str) -> dict:
    """Read the first few lines of a persisted log to extract summary fields."""
    info = {'filename': os.path.basename(path),
            'started_at': None, 'finished_at': None,
            'returncode': None, 'error': None,
            'size_bytes': 0, 'ok': None}
    try:
        info['size_bytes'] = os.path.getsize(path)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for _ in range(6):
                line = f.readline()
                if not line:
                    break
                if line.startswith('# started:'):
                    info['started_at'] = line.split(':', 1)[1].strip()
                elif line.startswith('# finished:'):
                    info['finished_at'] = line.split(':', 1)[1].strip()
                elif line.startswith('# returncode:'):
                    raw = line.split(':', 1)[1].strip()
                    info['returncode'] = int(raw) if raw.lstrip('-').isdigit() else None
                elif line.startswith('# error:'):
                    err = line.split(':', 1)[1].strip()
                    info['error'] = err if err else None
        info['ok'] = (info['error'] is None) and (info['returncode'] == 0)
    except Exception:
        pass
    return info


def _list_logs(limit: int = 30) -> list:
    """Return the most recent persisted sync logs, newest first."""
    try:
        entries = [e for e in os.listdir(SYNC_LOGS_DIR) if e.endswith('.log')]
    except FileNotFoundError:
        return []
    entries.sort(reverse=True)
    out = []
    for name in entries[:limit]:
        out.append(_parse_log_header(os.path.join(SYNC_LOGS_DIR, name)))
    return out


def _run_sync():
    """Background worker: run sync_live_data.bat and stream output into _state
    AND line-by-line to a disk log, so partial output survives crashes."""
    started_at = _state['started_at']
    running_path = _log_path_for(started_at, ok=None)
    _write_log_header(running_path, started_at, None, None, None)
    log_f = open(running_path, 'a', encoding='utf-8', errors='replace', buffering=1)
    try:
        proc = subprocess.Popen(
            ['cmd', '/c', SYNC_BAT],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=0x08000000,  # CREATE_NO_WINDOW on Windows
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            with _lock:
                _state['output'] += line
            log_f.write(line)
            log_f.flush()
        proc.wait()
        with _lock:
            _state['returncode'] = proc.returncode
    except Exception as e:
        logger.exception('[gemach.sync] sync process failed')
        with _lock:
            _state['error'] = str(e)
    finally:
        try:
            log_f.close()
        except Exception:
            pass
        with _lock:
            _state['running'] = False
            _state['finished_at'] = datetime.now().isoformat(timespec='seconds')
            snap = dict(_state)
        ok = (snap.get('error') is None) and (snap.get('returncode') == 0)
        final_path = _log_path_for(started_at, ok=ok)
        try:
            if running_path != final_path and os.path.isfile(running_path):
                os.replace(running_path, final_path)
        except Exception:
            logger.exception('[gemach.sync] failed to rename running log')
            final_path = running_path
        _write_log_header(final_path,
                          snap.get('started_at'), snap.get('finished_at'),
                          snap.get('returncode'), snap.get('error'))
        logger.info(f'[gemach.sync] persisted run to {os.path.basename(final_path)}')


@gemach_bp.route('/sync-access', methods=['GET'])
@gemach_required
def sync_access_page():
    return render_template('gemach/sync_access.html', history=_list_logs())


@gemach_bp.route('/sync-access/start', methods=['POST'])
@gemach_required
@csrf.exempt
def sync_access_start():
    with _lock:
        if _state['running']:
            return jsonify({'ok': False, 'error': 'already_running'}), 409
        if not os.path.isfile(SYNC_BAT):
            return jsonify({'ok': False, 'error': 'sync_live_data.bat not found'}), 500
        _state['running'] = True
        _state['started_at'] = datetime.now().isoformat(timespec='seconds')
        _state['finished_at'] = None
        _state['returncode'] = None
        _state['output'] = ''
        _state['error'] = None
    threading.Thread(target=_run_sync, daemon=True).start()
    return jsonify({'ok': True})


@gemach_bp.route('/sync-access/status', methods=['GET'])
@gemach_required
def sync_access_status():
    with _lock:
        snapshot = dict(_state)
    return jsonify(snapshot)


@gemach_bp.route('/sync-access/history', methods=['GET'])
@gemach_required
def sync_access_history():
    return jsonify({'runs': _list_logs()})


_SAFE_LOGNAME = re.compile(r'^[0-9T]+_(ok|fail|running)\.log$')


@gemach_bp.route('/sync-access/log/<name>', methods=['GET'])
@gemach_required
def sync_access_log(name):
    if not _SAFE_LOGNAME.match(name):
        abort(404)
    path = os.path.join(SYNC_LOGS_DIR, name)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype='text/plain; charset=utf-8')
