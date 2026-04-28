"""Runtime switch between local (SQLite) and remote (matattest MySQL) database.

State lives in `instance/db_mode.txt` (gitignored). Flipping the mode requires
an app restart because SQLAlchemy's engine is bound at startup.

The remote URL is pulled from env var DATABASE_URL_REMOTE — set it in .env
alongside DATABASE_URL, e.g.:

    DATABASE_URL=sqlite:///C:/Matat/instance/matat.db
    DATABASE_URL_REMOTE=mysql+pymysql://matat:<pw>@127.0.0.1:33306/matattest
"""
from __future__ import annotations

import os

LOCAL = 'local'
REMOTE = 'remote'

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODE_FILE = os.path.join(_PROJECT_ROOT, 'instance', 'db_mode.txt')


def get_db_mode() -> str:
    """Return 'local' or 'remote'. Defaults to 'local' if file missing/unreadable."""
    try:
        if os.path.isfile(MODE_FILE):
            with open(MODE_FILE, 'r', encoding='utf-8') as f:
                val = f.read().strip().lower()
            if val in (LOCAL, REMOTE):
                return val
    except OSError:
        pass
    return LOCAL


def set_db_mode(mode: str) -> None:
    """Persist 'local' or 'remote' to the mode file. Creates instance/ if needed."""
    if mode not in (LOCAL, REMOTE):
        raise ValueError(f'Unknown mode: {mode}')
    os.makedirs(os.path.dirname(MODE_FILE), exist_ok=True)
    with open(MODE_FILE, 'w', encoding='utf-8') as f:
        f.write(mode)


def resolve_database_url(mode: str | None = None, default: str | None = None) -> str:
    """Return the DATABASE_URL appropriate for the given mode.

    mode=None means read from the mode file. If mode='remote' but
    DATABASE_URL_REMOTE is not set, falls back to DATABASE_URL with a print warning.
    """
    if mode is None:
        mode = get_db_mode()
    if mode == REMOTE:
        remote = os.environ.get('DATABASE_URL_REMOTE')
        if remote:
            return remote
        print('[db_mode] remote mode selected but DATABASE_URL_REMOTE not set; '
              'falling back to DATABASE_URL.')
    return os.environ.get(
        'DATABASE_URL',
        default or 'mysql+pymysql://root:password@localhost:3306/matat',
    )
