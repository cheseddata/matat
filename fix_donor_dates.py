"""Fix donor created_at dates using their earliest donation date."""
import os, sys
from datetime import datetime
from sqlalchemy import text, func

sys.path.insert(0, '/var/www/matat')
os.environ['FLASK_APP'] = 'run.py'

from app import create_app
from app.extensions import db
from app.models import Donor, Donation

app = create_app()

with app.app_context():
    # Find donors created today that should have earlier dates
    today_donors = Donor.query.filter(
        func.date(Donor.created_at) == '2026-04-14',
        Donor.deleted_at.is_(None)
    ).all()

    print(f'Donors with today date to fix: {len(today_donors)}')

    fixed = 0
    for donor in today_donors:
        # Find their earliest donation
        earliest = Donation.query.filter_by(donor_id=donor.id).order_by(Donation.created_at).first()
        if earliest and earliest.created_at:
            donor.created_at = earliest.created_at
            fixed += 1
        else:
            # No donations - set to a reasonable default
            donor.created_at = datetime(2024, 1, 1)
            fixed += 1

    db.session.commit()
    print(f'Fixed: {fixed}')

    # Final verification
    result = db.session.execute(text("""
        SELECT
          CASE WHEN DATE(created_at) = '2026-04-14' THEN 'Still today'
               WHEN DATE(created_at) = '2020-01-01' THEN 'ZTorm (2020)'
               ELSE 'Correct date' END as category,
          COUNT(*) as count
        FROM donors WHERE deleted_at IS NULL
        GROUP BY category
    """)).fetchall()
    for row in result:
        print(f'  {row[0]}: {row[1]}')
