"""Wedding tracking — replaces the Word-doc list of upcoming weddings.

The org helps fund weddings for those in need ("Assisting the needy for
their weddings" is a Matat fund category). The operator used to keep an
unstructured list in a Word document; this model gives that list a
proper home so we can sort/filter/print and eventually link it to the
donations that funded each wedding.
"""
from datetime import datetime
from ..extensions import db


class Wedding(db.Model):
    __tablename__ = 'weddings'

    id = db.Column(db.Integer, primary_key=True)

    # Hebrew date — free-text the way the operator writes it (e.g. "א' סיון",
    # "כ\"ה אדר א'", "ל' חשון תשפ\"ו"). Single string keeps entry fast and
    # matches how it appeared in the Word doc.
    hebrew_date = db.Column(db.String(80), nullable=False)
    # Optional Gregorian equivalent so we can sort chronologically and put
    # weddings on a calendar later.
    gregorian_date = db.Column(db.Date, nullable=True)

    # Names exactly as the operator types them — Hebrew, English, mix, all OK.
    groom_name = db.Column(db.String(120), nullable=False)
    bride_name = db.Column(db.String(120), nullable=False)

    # Venue + how to reach the family.
    hall_name = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    contact_name = db.Column(db.String(120), nullable=True)

    # Free-form column for anything else: amount pledged, kallah's family
    # situation, who referred them, dietary notes, etc.
    notes = db.Column(db.Text, nullable=True)

    # Operator-driven "hide from default view". Soft-delete (deleted_at)
    # is for actual data removal; `hidden` is for "this wedding already
    # happened / I don't want it in the active list, but keep the record".
    hidden = db.Column(db.Boolean, nullable=False, default=False, server_default='0')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)  # soft delete

    # Author so we know who entered the record.
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))

    def __repr__(self):
        return f'<Wedding {self.id} {self.groom_name} & {self.bride_name} on {self.hebrew_date}>'
