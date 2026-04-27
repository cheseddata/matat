"""Bulk-regenerate the on-disk PDF for every US receipt so it picks up
the new template (zip-code fix, transaction box, etc.). DOES NOT email.

A "US receipt" here = donor.country is one of US/USA/United States, or empty
(empty defaults to US in our admin form). Israeli receipts are skipped —
they go through YeshInvoice on a separate flow.

Run on the server:
    cd /var/www/matat && source venv/bin/activate && python bulk_regen_us_receipts.py [--dry-run]
"""
import sys
sys.path.insert(0, '/var/www/matat')
from app import create_app
from app.extensions import db
from app.models.donor import Donor
from app.models.donation import Donation
from app.models.receipt import Receipt
from app.services.receipt_service import regenerate_receipt_pdf

DRY = '--dry-run' in sys.argv

app = create_app()
with app.app_context():
    rows = (Receipt.query
            .join(Donor, Donor.id == Receipt.donor_id)
            .filter(Donor.country.in_([
                'US', 'USA', 'United States', 'United States of America',
                'us', 'usa', 'America', None, ''
            ]))
            .order_by(Receipt.id)
            .all())
    print(f'Found {len(rows)} US receipt(s).')
    if DRY:
        for r in rows[:20]:
            d = Donor.query.get(r.donor_id)
            print(f'  {r.receipt_number}  donor#{r.donor_id} {d.first_name} {d.last_name} ({d.country!r})  pdf={r.pdf_path}')
        print(f'... and {max(0, len(rows)-20)} more')
        print('DRY RUN — nothing regenerated. Pass without --dry-run to actually rewrite.')
        sys.exit(0)

    ok = fail = skipped = 0
    for r in rows:
        if not r.pdf_path:
            skipped += 1
            continue
        try:
            new_path = regenerate_receipt_pdf(r)
            if new_path:
                ok += 1
            else:
                fail += 1
                print(f'  FAIL {r.receipt_number}: regenerate returned None')
        except Exception as e:
            fail += 1
            print(f'  FAIL {r.receipt_number}: {e}')
    print(f'Regenerated: {ok}    Failed: {fail}    Skipped (no pdf_path): {skipped}')
