"""Gemach Member (חבר / Haver) — person in the Gmach loan / fund system."""
from datetime import datetime
from ..extensions import db


class GemachMember(db.Model):
    """A member of the Gmach charitable fund. Often a loan borrower.

    Can be linked to an existing Donor record via donor_id (via TZ/email/name match
    or via the legacy ztorm_donor_id cross-reference).
    Preserves the legacy gmach_card_no so the original Access data can be re-imported.
    """
    __tablename__ = 'gemach_members'

    id = db.Column(db.Integer, primary_key=True)

    # Legacy card_no preserved for import/switchover
    gmach_card_no = db.Column(db.Integer, unique=True, nullable=False, index=True)

    # Optional link to existing Donor (when matched via TZ/email/name)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='SET NULL'),
                         nullable=True, index=True)

    # Cross-reference to ZTorm (if member is also a ZTorm donor)
    ztorm_donor_id = db.Column(db.Integer, nullable=True, index=True)

    # Identity
    last_name = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    title = db.Column(db.String(12))           # toar
    suffix = db.Column(db.String(20))          # siomet
    teudat_zehut = db.Column(db.String(9))     # t_z (stored as string to preserve leading zeros)
    member_type = db.Column(db.String(5))      # sug

    # Primary contact
    address = db.Column(db.String(70))
    city = db.Column(db.String(25))
    zip_code = db.Column(db.String(10))        # mikud
    phone = db.Column(db.String(15))
    phone_area = db.Column(db.String(3))
    phone2 = db.Column(db.String(15))          # tel_nosaf
    phone2_area = db.Column(db.String(3))
    fax = db.Column(db.String(15))
    fax_area = db.Column(db.String(3))

    # Secondary contact (optional)
    address2_type = db.Column(db.String(7))    # sug_ctovet_2
    address2_name = db.Column(db.String(30))   # shem_makom_2
    address2 = db.Column(db.String(70))
    city2 = db.Column(db.String(25))
    zip_code2 = db.Column(db.String(10))
    phone2_secondary = db.Column(db.String(15))  # tel_2
    phone2_secondary_area = db.Column(db.String(3))
    fax2 = db.Column(db.String(15))
    fax2_area = db.Column(db.String(3))

    # Mail address selector (1=primary, 2=secondary)
    mail_address = db.Column(db.SmallInteger, default=1)

    # Classifications (5 tag slots from Access sivug_1..5)
    tag1 = db.Column(db.String(5))
    tag2 = db.Column(db.String(5))
    tag3 = db.Column(db.String(5))
    tag4 = db.Column(db.String(5))
    tag5 = db.Column(db.String(5))

    # Flags and preferences
    bookmark = db.Column(db.Boolean, default=False)      # simun
    english_receipt = db.Column(db.Boolean, default=False)  # kabala_eng

    # Dates
    registration_date = db.Column(db.Date)     # date_klita
    last_reconciliation = db.Column(db.Date)   # date_idcun_aharon

    # Notes
    notes = db.Column(db.Text)                 # heara

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    donor = db.relationship('Donor', backref=db.backref('gemach_member', uselist=False),
                            foreign_keys=[donor_id])

    @property
    def full_name(self):
        parts = [self.title, self.first_name, self.last_name, self.suffix]
        return ' '.join(p for p in parts if p)

    @property
    def primary_phone(self):
        if self.phone_area and self.phone:
            return f"{self.phone_area}-{self.phone}"
        return self.phone or ''

    def __repr__(self):
        return f'<GemachMember card_no={self.gmach_card_no} {self.last_name}>'
