"""Gemach Institution (מוסד / Mosad) — fund source organization."""
from datetime import datetime
from ..extensions import db


class GemachInstitution(db.Model):
    __tablename__ = 'gemach_institutions'

    id = db.Column(db.Integer, primary_key=True)
    gmach_num_mosad = db.Column(db.SmallInteger, unique=True, nullable=False, index=True)

    name = db.Column(db.String(50), nullable=False)  # shem_mosad
    code = db.Column(db.String(20))                  # code_mosad (tax ID)
    active = db.Column(db.Boolean, default=True)    # pail

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<GemachInstitution {self.gmach_num_mosad} {self.name}>'
