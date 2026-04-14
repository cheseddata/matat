from datetime import datetime
from ..extensions import db


class Donor(db.Model):
    """Donor information."""
    __tablename__ = 'donors'

    id = db.Column(db.Integer, primary_key=True)
    stripe_customer_id = db.Column(db.String(255), unique=True, nullable=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    phone_country_code = db.Column(db.String(10), nullable=True)
    teudat_zehut = db.Column(db.String(9), nullable=True)  # Israeli ID number
    address_line1 = db.Column(db.String(255), nullable=True)
    address_line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    zip = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), default='US')
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
        return f"{self.first_name} {self.last_name}"

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
