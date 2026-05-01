from datetime import datetime
from flask_login import UserMixin
from sqlalchemy.ext.mutable import MutableList
from ..extensions import db


class User(UserMixin, db.Model):
    """Admin and salesperson accounts."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='salesperson')  # admin/salesperson
    ref_code = db.Column(db.String(50), unique=True, nullable=True)  # e.g., SP-0042
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    is_temp_password = db.Column(db.Boolean, default=True)
    commission_type = db.Column(db.String(20), nullable=True)  # flat/percentage
    commission_rate = db.Column(db.Numeric(10, 2), nullable=True)
    commission_tiers = db.Column(db.JSON, nullable=True)  # For tiered rates
    language_pref = db.Column(db.String(5), default='en')  # en/he
    active = db.Column(db.Boolean, default=True)
    # Processor permission: null/empty = all processors allowed; else list of processor codes
    allowed_processors = db.Column(MutableList.as_mutable(db.JSON), nullable=True)
    # When True a salesperson sees the full /admin/donations list (not just their own).
    # Admins are always treated as True regardless of this flag.
    can_view_all_donations = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    # Charity tabs the user wants surfaced on /admin/donations as quick
    # filter buttons. Empty / null = no charity tab strip rendered (the
    # default — keeps the page clean for users who don't track charities).
    # Operator picks which charities to show via /admin/donation-permissions.
    visible_charities = db.Column(MutableList.as_mutable(db.JSON), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    claude_notes = db.Column(db.Text, nullable=True)  # Context for Claude about this user
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    donations = db.relationship('Donation', backref='salesperson', lazy='dynamic',
                                foreign_keys='Donation.salesperson_id')
    commissions = db.relationship('Commission', backref='salesperson', lazy='dynamic')
    donation_links = db.relationship('DonationLink', backref='salesperson', lazy='dynamic')
    campaigns_created = db.relationship('Campaign', backref='creator', lazy='dynamic')
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.username
    
    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    def can_view_processor(self, processor_code):
        """True if user may view donations from this processor.

        An empty/null allow-list means access to every processor.
        The restriction applies regardless of role (including admins) so
        specific admins can be scoped to a single processor when needed.
        """
        if not self.allowed_processors:
            return True
        return processor_code in self.allowed_processors

    def __repr__(self):
        return f'<User {self.username}>'
