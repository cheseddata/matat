from datetime import datetime
from ..extensions import db


class MemorialName(db.Model):
    """Yahrzeit / memorial names (ZTorm: ShemotAzcara)."""
    __tablename__ = 'memorial_names'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='CASCADE'), nullable=False)
    agreement_id = db.Column(db.Integer, db.ForeignKey('agreements.id'), nullable=True)

    name = db.Column(db.String(200), nullable=False)  # name of deceased
    parent_name = db.Column(db.String(200), nullable=True)  # parent
    relationship = db.Column(db.String(50), nullable=True)  # relation: av/em/ach/etc.
    relationship_to_donor = db.Column(db.String(50), nullable=True)  # relation_torem
    memorial_type = db.Column(db.String(20), nullable=True)  # sug

    # Hebrew date of passing
    hebrew_day = db.Column(db.Integer, nullable=True)  # yom
    hebrew_month = db.Column(db.Integer, nullable=True)  # hodesh
    hebrew_year = db.Column(db.Integer, nullable=True)  # shana

    # Kadish
    kadish_end_date = db.Column(db.Date, nullable=True)  # sium_kadish_yomi
    is_active = db.Column(db.Boolean, default=True)  # pail
    is_agreement_only = db.Column(db.Boolean, default=False)  # hescem_only

    notes = db.Column(db.Text, nullable=True)  # heara

    registration_date = db.Column(db.Date, nullable=True)  # date_klita
    last_print_date = db.Column(db.Date, nullable=True)  # azcara_print

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<MemorialName {self.name}>'
