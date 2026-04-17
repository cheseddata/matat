"""Seed a fresh matat.db with an admin user + default ConfigSettings.

Idempotent — safe to run multiple times; only adds what's missing.

Usage:
    venv\\Scripts\\python.exe sync\\seed_admin.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MATAT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(MATAT_DIR))
os.chdir(MATAT_DIR)

from app import create_app
from app.extensions import db, bcrypt
from app.models import User, ConfigSettings


def main():
    app = create_app('development')
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@matatmordechai.org',
                role='admin',
                first_name='Admin',
                last_name='User',
            )
            if hasattr(admin, 'is_temp_password'):
                admin.is_temp_password = False
            if hasattr(admin, 'is_active'):
                admin.is_active = True
            admin.password_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
            db.session.add(admin)
            print('Created admin user (admin / admin123)')
        else:
            print('Admin user already exists')

        cfg = ConfigSettings.query.first()
        if not cfg:
            cfg = ConfigSettings(
                org_name='Matat Mordechai',
                org_prefix='MM',
            )
            db.session.add(cfg)
            print('Created default ConfigSettings')
        else:
            print('ConfigSettings already present')

        db.session.commit()
        print('Seed complete.')


if __name__ == '__main__':
    main()
