"""One-shot — re-send receipts for the two unknown-donor charges we
recovered earlier today. The originals went to unknown@example.com
because the webhook hadn't read billing_details off the charge yet.

#6736 Kalman Berenbaum  $18.00  receipt MM-2026-00399 exists
                                → regenerate PDF + resend to real email
#6714 Adam Lieberman    $30.00  no receipt yet
                                → create_receipt_atomic + send

#6716 Miriam Rosen $1 test — SKIPPED (operator's own test charge,
won't bother sending her a real receipt for a self-test).
"""
from app import create_app
from app.extensions import db
from app.models.donation import Donation
from app.models.receipt import Receipt
from app.services.receipt_service import (
    create_receipt_atomic, regenerate_receipt_pdf
)
from app.services.email_service import send_receipt_email


def main():
    app = create_app()
    with app.app_context():
        # ----- #6736 Kalman: receipt exists, just regenerate + resend
        d = Donation.query.get(6736)
        r = Receipt.query.filter_by(donation_id=d.id).first()
        print(f'#{d.id} Kalman — regenerating PDF for {r.receipt_number}')
        regenerate_receipt_pdf(r)
        ok = send_receipt_email(d.donor, d, r)
        print(f'   email→ {d.donor.email}  {"OK" if ok else "FAIL"}')

        # ----- #6714 Adam: no receipt, create then send
        d2 = Donation.query.get(6714)
        print(f'\n#{d2.id} Adam Lieberman — creating receipt')
        r2 = create_receipt_atomic(d2, d2.donor)
        db.session.commit()
        print(f'   receipt {r2.receipt_number} created')
        ok = send_receipt_email(d2.donor, d2, r2)
        print(f'   email→ {d2.donor.email}  {"OK" if ok else "FAIL"}')

        db.session.commit()
        print('\ndone.')


if __name__ == '__main__':
    main()
