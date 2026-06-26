"""One-shot — recover donor name+email for the 3 unknown stripe donations
from June 22-26 2026 by reading billing_details directly off Stripe.

Donations to fix:
  #6736  2026-06-26  $18.00  pi_3TmcLSLpYYqBobrr2J8JNgbw
  #6716  2026-06-22  $1.00   pi_3Tl1hGLpYYqBobrr1VxdK0lE
  #6714  2026-06-22  $30.00  pi_3Tkve2LpYYqBobrr0v8mnNrZ

For each: retrieve PI with latest_charge expanded → read billing_details
→ if a donor with that email already exists, re-link the donation to
them and soft-delete the placeholder donor row; otherwise update the
placeholder in place to the real values.
"""
import os, stripe
from app import create_app
from app.extensions import db
from app.models.donation import Donation
from app.models.donor import Donor
from app.models.config_settings import ConfigSettings
from datetime import datetime

TARGETS = [
    ('6736', 'pi_3TmcLSLpYYqBobrr2J8JNgbw'),
    ('6716', 'pi_3Tl1hGLpYYqBobrr1VxdK0lE'),
    ('6714', 'pi_3Tkve2LpYYqBobrr0v8mnNrZ'),
]


def main():
    app = create_app()
    with app.app_context():
        c = ConfigSettings.query.first()
        stripe.api_key = c.stripe_live_secret_key or os.environ.get('STRIPE_LIVE_SECRET_KEY')

        for did_str, pi_id in TARGETS:
            d = Donation.query.get(int(did_str))
            if not d:
                print(f'#{did_str}: not found, skipping')
                continue
            pi = stripe.PaymentIntent.retrieve(pi_id, expand=['latest_charge'])
            bd = pi.latest_charge.billing_details
            email = (bd.email or '').strip().lower()
            name = (bd.name or '').strip()
            if not email:
                print(f'#{did_str}: no email on billing_details, skipping')
                continue

            parts = name.split(None, 1)
            first = parts[0] if parts else 'Unknown'
            last  = parts[1] if len(parts) > 1 else 'Donor'

            old_donor = d.donor
            existing = Donor.query.filter(
                db.func.lower(Donor.email) == email,
                Donor.id != old_donor.id,
            ).first()

            if existing:
                # Re-link donation to the existing real donor
                d.donor_id = existing.id
                # Keep the placeholder for audit but mark deleted
                if old_donor and (old_donor.email or '').startswith('unknown@'):
                    old_donor.deleted_at = datetime.utcnow()
                print(f'#{did_str}: re-linked to existing donor #{existing.id} '
                      f'({existing.first_name} {existing.last_name} <{existing.email}>) '
                      f'— placeholder donor #{old_donor.id} soft-deleted')
            else:
                # Update placeholder in place
                old_donor.first_name = first
                old_donor.last_name  = last
                old_donor.email      = email
                print(f'#{did_str}: updated donor #{old_donor.id} → '
                      f'{first} {last} <{email}>')

        db.session.commit()
        print('\ndone.')


if __name__ == '__main__':
    main()
