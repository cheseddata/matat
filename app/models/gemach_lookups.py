"""Gemach lookup tables: cancellation reasons, transaction types, chart of accounts, memorials."""
from datetime import datetime
from ..extensions import db


class GemachCancellationReason(db.Model):
    """Sibot_bitul — codes for cancellation and bounce reasons.

    17 legacy codes like אח (no signature), בח (cancelled debt), etc.
    """
    __tablename__ = 'gemach_cancellation_reasons'

    code = db.Column(db.String(2), primary_key=True)  # code_siba
    name = db.Column(db.String(255), nullable=False)  # shem_siba
    triggers_cancellation = db.Column(db.Boolean, default=False)  # lvatel


class GemachTransactionType(db.Model):
    """Sugei_Tnua — 5 transaction type codes: הלו/תרו/פקד/תמי/הוצ."""
    __tablename__ = 'gemach_transaction_types'

    code = db.Column(db.String(3), primary_key=True)  # sug_tnua
    description = db.Column(db.String(50), nullable=False)  # teur


class GemachHashAccount(db.Model):
    """HashAccts — chart of accounts for external accounting export."""
    __tablename__ = 'gemach_hash_accounts'

    account_no = db.Column(db.Integer, primary_key=True)  # acct_no
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(50))


class GemachMemorial(db.Model):
    """Munz — memorial/yahrzeit records sponsored by a member.

    Empty in current data but structure is preserved.
    """
    __tablename__ = 'gemach_memorials'

    id = db.Column(db.Integer, primary_key=True)
    gmach_id = db.Column(db.Integer, index=True)

    sponsor_member_id = db.Column(db.Integer, db.ForeignKey('gemach_members.id', ondelete='CASCADE'),
                                  nullable=False, index=True)

    deceased_name = db.Column(db.String(100))  # name
    hebrew_day = db.Column(db.SmallInteger)    # yom
    hebrew_month = db.Column(db.String(10))    # hodesh
    hebrew_year = db.Column(db.SmallInteger)   # shana

    active = db.Column(db.Boolean, default=True)   # pail
    kaddish_end_date = db.Column(db.Date)          # sium_kadish_yomi

    registration_date = db.Column(db.Date)   # date_klita
    yahrzeit_printed = db.Column(db.Boolean, default=False)  # hudpas_tizcoret
    kaddish_printed = db.Column(db.Boolean, default=False)   # hudpas_kadish

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sponsor = db.relationship('GemachMember',
                              backref=db.backref('memorials', lazy='dynamic'))


class GemachSetup(db.Model):
    """Setup — system configuration key-value pairs.

    Typically contains ~1 row per config key (legacy Access INI-style).
    """
    __tablename__ = 'gemach_setup'

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255))
    description = db.Column(db.String(50))
