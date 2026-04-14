"""Fix Nedarim donation created_at dates using TransactionTime from metadata."""
import os, sys, json
from datetime import datetime

sys.path.insert(0, '/var/www/matat')
os.environ['FLASK_APP'] = 'run.py'

from app import create_app
from app.extensions import db
from app.models import Donation

app = create_app()

with app.app_context():
    nedarim = Donation.query.filter_by(payment_processor='nedarim').all()
    print(f'Nedarim donations to fix: {len(nedarim)}')

    fixed = 0
    errors = 0
    for d in nedarim:
        try:
            if d.processor_metadata and isinstance(d.processor_metadata, dict):
                tx_time = d.processor_metadata.get('TransactionTime', '')
                if tx_time:
                    original_date = datetime.strptime(tx_time, '%d/%m/%Y %H:%M:%S')
                    d.created_at = original_date
                    fixed += 1
        except Exception as e:
            errors += 1
            if errors < 5:
                print(f'  Error on donation {d.id}: {e}')

    db.session.commit()
    print(f'Fixed: {fixed}, Errors: {errors}')

    # Verify
    from sqlalchemy import text
    result = db.session.execute(text(
        "SELECT MIN(created_at), MAX(created_at) FROM donations WHERE payment_processor='nedarim'"
    )).first()
    print(f'Date range now: {result[0]} to {result[1]}')
