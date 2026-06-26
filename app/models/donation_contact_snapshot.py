"""Per-transaction donor-contact snapshot — captures what the donor
typed for THIS specific donation, regardless of what's already on
the canonical Donor record.

Rationale: the canonical Donor row is the operator's source-of-truth
identity for a person (their "main" name/email/address/phone). But on
any given transaction the donor may type a different email (e.g., a
work address for a tax receipt), a fresh phone, a different shipping
address — and we want to preserve all of that without overwriting the
main record every time.

Used by the filter-fallback Stripe Payment Link flow today (the
checkout.session.completed webhook writes one per donation), but the
schema is generic — any future donation source can write a row here.

Receipt-routing rule: if snapshot.email differs from donor.email,
send the receipt to snapshot.email first; on bounce, fall back to
donor.email. (Bounce detection wired separately via the Exchange
inbox DSN sweep.)
"""
from datetime import datetime
from ..extensions import db
from sqlalchemy.ext.mutable import MutableDict


class DonationContactSnapshot(db.Model):
    __tablename__ = 'donation_contact_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(
        db.Integer,
        db.ForeignKey('donations.id', ondelete='CASCADE'),
        unique=True, nullable=False, index=True,
    )
    donor_id = db.Column(
        db.Integer,
        db.ForeignKey('donors.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    # As-entered fields for this transaction
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    company_name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(255), nullable=True, index=True)
    phone = db.Column(db.String(50), nullable=True)
    address_line1 = db.Column(db.String(255), nullable=True)
    address_line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    zip = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(50), nullable=True)

    # Receipt-delivery tracking (per-snapshot, not per-donor)
    receipt_sent_to_email = db.Column(db.String(255), nullable=True)
    receipt_bounced = db.Column(db.Boolean, default=False, nullable=False)
    receipt_fallback_used = db.Column(db.Boolean, default=False, nullable=False)
    receipt_bounce_reason = db.Column(db.String(500), nullable=True)

    # Provenance — where did the data come from
    # 'stripe_checkout', 'stripe_elements', 'nedarim_plus', 'manual', etc.
    source = db.Column(db.String(50), nullable=True)
    # Raw provider payload kept verbatim for later audit / migration
    raw_data = db.Column(MutableDict.as_mutable(db.JSON), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    donor = db.relationship('Donor')
    donation = db.relationship(
        'Donation',
        backref=db.backref('contact_snapshot', uselist=False,
                           cascade='all, delete-orphan'),
    )

    def __repr__(self):
        return (f'<DonationContactSnapshot donation_id={self.donation_id} '
                f'email={self.email!r} src={self.source!r}>')
