from datetime import datetime
from ..extensions import db


class Donor(db.Model):
    """Donor information."""
    __tablename__ = 'donors'

    id = db.Column(db.Integer, primary_key=True)
    stripe_customer_id = db.Column(db.String(255), unique=True, nullable=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    hebrew_first_name = db.Column(db.String(100), nullable=True, index=True)  # שם פרטי בעברית — searchable
    hebrew_last_name = db.Column(db.String(100), nullable=True, index=True)   # שם משפחה בעברית — searchable
    company_name = db.Column(db.String(200), nullable=True)  # e.g. 'ABC Corporation' — shown on receipt
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    phone_country_code = db.Column(db.String(10), nullable=True)
    # Structured phones — Israeli vs foreign × home/cell/fax. The legacy
    # `phone` column stays as a primary/SMS-target field, kept in sync
    # server-side from whichever cell field was last touched.
    il_phone_home = db.Column(db.String(50), nullable=True)
    il_phone_cell = db.Column(db.String(50), nullable=True)
    il_phone_fax = db.Column(db.String(50), nullable=True)
    foreign_phone_home = db.Column(db.String(50), nullable=True)
    foreign_phone_cell = db.Column(db.String(50), nullable=True)
    foreign_phone_fax = db.Column(db.String(50), nullable=True)
    teudat_zehut = db.Column(db.String(9), nullable=True)  # Israeli ID number
    address_line1 = db.Column(db.String(255), nullable=True)
    address_line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    zip = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), default='US')

    # Israeli address (for donors with dual addresses)
    il_address_line1 = db.Column(db.String(255), nullable=True)
    il_address_line2 = db.Column(db.String(255), nullable=True)
    il_city = db.Column(db.String(100), nullable=True)
    il_zip = db.Column(db.String(20), nullable=True)
    il_phone = db.Column(db.String(50), nullable=True)       # Israeli home phone
    il_phone_cell = db.Column(db.String(50), nullable=True)  # Israeli cell phone
    phone_cell = db.Column(db.String(50), nullable=True)     # Foreign cell phone

    comm_pref_email = db.Column(db.Boolean, default=True)
    comm_pref_sms = db.Column(db.Boolean, default=False)
    comm_pref_whatsapp = db.Column(db.Boolean, default=False)
    language_pref = db.Column(db.String(5), default='en')  # en/he
    test = db.Column(db.Boolean, default=False)  # True for test donations, False for real
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Link duplicate donors to a primary record
    primary_donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=True)

    # External system integration (for imports from third-party software)
    external_id = db.Column(db.String(100), nullable=True, index=True)  # ID from external system
    external_source = db.Column(db.String(50), nullable=True)  # e.g., 'salesforce', 'bloomerang', 'csv_import'

    # Multi-office segregation: each donor is "owned" by one user account.
    # Admin/salesperson views filter by this field so each office sees only
    # their own donors. NULL = unassigned (legacy / migrating). Existing
    # donors at rollout were backfilled to user_id=4 (Gittle Goldblum).
    owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    # === ZTORM FIELDS ===
    ztorm_donor_id = db.Column(db.Integer, nullable=True, index=True)
    title = db.Column(db.String(50), nullable=True)
    suffix = db.Column(db.String(50), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    spouse_name = db.Column(db.String(100), nullable=True)
    spouse_tz = db.Column(db.String(9), nullable=True)
    father_name = db.Column(db.String(100), nullable=True)
    mother_name = db.Column(db.String(100), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    birth_year = db.Column(db.Integer, nullable=True)
    occupation = db.Column(db.String(100), nullable=True)
    send_mail = db.Column(db.Boolean, default=True)
    mail_reason = db.Column(db.String(255), nullable=True)
    receipt_name = db.Column(db.String(200), nullable=True)
    receipt_tz = db.Column(db.String(9), nullable=True)
    send_receipts_once = db.Column(db.Boolean, default=False)
    send_receipts_yearly = db.Column(db.Boolean, default=False)
    monthly_receipt = db.Column(db.Boolean, default=False)
    receipt_tz_not_required = db.Column(db.Boolean, default=False)
    letter_first_name = db.Column(db.String(100), nullable=True)
    letter_last_name = db.Column(db.String(100), nullable=True)
    letter_title = db.Column(db.String(50), nullable=True)
    letter_suffix = db.Column(db.String(50), nullable=True)
    classification_1 = db.Column(db.String(100), nullable=True)
    classification_2 = db.Column(db.String(100), nullable=True)
    classification_3 = db.Column(db.String(100), nullable=True)
    classification_4 = db.Column(db.String(100), nullable=True)
    classification_5 = db.Column(db.String(100), nullable=True)
    bookmark = db.Column(db.Boolean, default=False)
    follow_up_freq = db.Column(db.Integer, nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    registration_date = db.Column(db.Date, nullable=True)

    # Relationships
    donations = db.relationship('Donation', backref='donor', lazy='dynamic')
    receipts = db.relationship('Receipt', backref='donor', lazy='dynamic')
    addresses = db.relationship('Address', backref='donor', lazy='dynamic')
    phones = db.relationship('Phone', backref='donor', lazy='dynamic')
    memorial_names = db.relationship('MemorialName', backref='donor', lazy='dynamic')
    communications = db.relationship('Communication', backref='donor', lazy='dynamic')

    # Self-referential relationship for linked donors
    linked_donors = db.relationship(
        'Donor',
        backref=db.backref('primary_donor', remote_side=[id]),
        lazy='dynamic'
    )
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def display_name(self):
        parts = []
        if self.title: parts.append(self.title)
        parts.append(self.first_name)
        parts.append(self.last_name)
        if self.suffix: parts.append(self.suffix)
        return ' '.join(filter(None, parts))

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @property
    def receipt_primary_name(self):
        """Name to render on the receipt's primary 'made out to' line.

        If the donor has no personal name (company-only donations), use the
        company name as the primary line; otherwise use the person's full name.
        """
        name = self.full_name
        if name:
            return name
        return self.company_name or ''

    @property
    def has_personal_name(self):
        return bool(self.full_name)

    @property
    def full_address(self):
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        if self.city and self.state and self.zip:
            parts.append(f"{self.city}, {self.state} {self.zip}")
        elif self.city:
            parts.append(self.city)
        return '\n'.join(filter(None, parts))

    @property
    def is_primary(self):
        """True if this is a primary donor record (not linked to another)."""
        return self.primary_donor_id is None

    @property
    def effective_primary(self):
        """Get the primary donor record (self if primary, otherwise the linked primary)."""
        if self.primary_donor_id:
            return Donor.query.get(self.primary_donor_id)
        return self

    def get_all_linked_donors(self):
        """Get all donors linked to this one (including self if primary)."""
        if self.primary_donor_id:
            # This is a linked donor, get the primary and its links
            primary = Donor.query.get(self.primary_donor_id)
            if primary:
                return [primary] + list(primary.linked_donors.all())
            return [self]
        else:
            # This is a primary donor
            return [self] + list(self.linked_donors.all())

    def get_all_donations(self):
        """Get all donations across this donor and all linked donors."""
        from .donation import Donation
        all_donors = self.get_all_linked_donors()
        donor_ids = [d.id for d in all_donors]
        return Donation.query.filter(Donation.donor_id.in_(donor_ids)).order_by(Donation.created_at.desc()).all()

    def get_total_donated(self):
        """Get total amount donated across all linked donors."""
        from .donation import Donation
        from sqlalchemy import func
        all_donors = self.get_all_linked_donors()
        donor_ids = [d.id for d in all_donors]
        total = db.session.query(func.sum(Donation.amount)).filter(
            Donation.donor_id.in_(donor_ids),
            Donation.status == 'succeeded'
        ).scalar()
        return total or 0

    def get_all_emails(self):
        """Get all email addresses for this person (across linked donors)."""
        all_donors = self.get_all_linked_donors()
        return list(set(d.email for d in all_donors if d.email))

    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    @classmethod
    def find_by_external_id(cls, external_id, source=None):
        """Find donor by external system ID."""
        query = cls.query.filter(cls.external_id == external_id)
        if source:
            query = query.filter(cls.external_source == source)
        return query.first()

    def __repr__(self):
        return f'<Donor {self.email}>'


# ----------------------------------------------------------------------
# Auto-assign owner_user_id on insert (multi-office segregation)
# ----------------------------------------------------------------------
# Every new Donor gets `owner_user_id` set automatically:
#   1. If the caller already set it, leave it alone.
#   2. Else use the current logged-in user (web request context).
#   3. Else fall back to DEFAULT_OWNER_USER_ID (env / Flask config / hardcoded 4).
#
# The fallback exists so background jobs (Stripe webhook, Nedarim sync, CSV
# import) that have no `current_user` still produce ownership-attributed
# donors instead of orphaned NULLs. The default starts as Gittle Goldblum
# (user_id=4) per the 2026-04-29 multi-office rollout; change it via the
# `MATAT_DEFAULT_OWNER_USER_ID` env var or Flask config when the office
# routing matrix matures.
from sqlalchemy import event
from flask import has_app_context, current_app


_DEFAULT_OWNER_FALLBACK = 4  # Gittle Goldblum at rollout (2026-04-29)


@event.listens_for(Donor, 'before_insert')
def _set_donor_owner(mapper, connection, target):
    if target.owner_user_id is not None:
        return
    # Try logged-in user (web request)
    try:
        from flask_login import current_user
        if current_user and getattr(current_user, 'is_authenticated', False):
            uid = getattr(current_user, 'id', None)
            if uid:
                target.owner_user_id = uid
                return
    except Exception:
        pass
    # Fall back to configured default
    default = _DEFAULT_OWNER_FALLBACK
    if has_app_context():
        default = current_app.config.get('DEFAULT_OWNER_USER_ID', default)
    import os
    default = int(os.environ.get('MATAT_DEFAULT_OWNER_USER_ID', default))
    target.owner_user_id = default
