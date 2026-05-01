from datetime import datetime
from ..extensions import db


class Donation(db.Model):
    """All donation transactions."""
    __tablename__ = 'donations'
    
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id', ondelete='RESTRICT'), nullable=False)
    salesperson_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='RESTRICT'), nullable=True)
    link_id = db.Column(db.Integer, db.ForeignKey('donation_links.id', ondelete='SET NULL'), nullable=True)
    
    # Payment processor tracking (generic fields for all processors)
    payment_processor = db.Column(db.String(50), default='stripe')  # 'stripe', 'nedarim', 'cardcom', etc.
    processor_transaction_id = db.Column(db.String(255), nullable=True)  # Generic transaction ID
    processor_confirmation = db.Column(db.String(255), nullable=True)  # Authorization/confirmation code
    processor_token = db.Column(db.String(255), nullable=True)  # Saved payment token for recurring
    processor_recurring_id = db.Column(db.String(255), nullable=True)  # Recurring/subscription/keva ID
    processor_fee = db.Column(db.Integer, nullable=True)  # Fee in cents/agorot
    processor_fee_currency = db.Column(db.String(10), nullable=True)  # Fee currency
    processor_metadata = db.Column(db.JSON, nullable=True)  # Processor-specific data
    processor_receipt_url = db.Column(db.String(500), nullable=True)  # External receipt URL (CardCom, iCount)
    routing_reason = db.Column(db.String(255), nullable=True)  # Why this processor was selected
    donor_country = db.Column(db.String(5), nullable=True)  # Country code for routing

    # Stripe fields
    stripe_payment_intent_id = db.Column(db.String(255), unique=True, nullable=True)
    stripe_charge_id = db.Column(db.String(255), nullable=True)
    stripe_balance_transaction_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    stripe_receipt_url = db.Column(db.String(500), nullable=True)
    stripe_metadata = db.Column(db.JSON, nullable=True)

    # Nedarim Plus fields
    nedarim_transaction_id = db.Column(db.String(255), unique=True, nullable=True)
    nedarim_confirmation = db.Column(db.String(255), nullable=True)
    nedarim_keva_id = db.Column(db.String(255), nullable=True)  # Standing order ID for recurring

    # YeshInvoice fields
    yeshinvoice_doc_id = db.Column(db.String(255), nullable=True)
    yeshinvoice_doc_number = db.Column(db.String(100), nullable=True)
    yeshinvoice_pdf_url = db.Column(db.String(500), nullable=True)
    # הקצאה / law number / tax-authority approval number — populated by
    # the YeshInvoice webhook callback after רשות המסים allocates a
    # number for the document. NOT available in the createDocument
    # response; only delivered via the /webhooks/yeshinvoice endpoint.
    yeshinvoice_allocation_number = db.Column(db.String(50), nullable=True, index=True)

    # DAF (Donor-Advised Fund) fields
    is_daf_donation = db.Column(db.Boolean, default=False)  # True for DAF/charity card donations
    daf_provider = db.Column(db.String(100), nullable=True)  # "The Donors Fund", "OJC Fund", "JCF", "Matbia", etc.
    daf_grant_id = db.Column(db.String(255), nullable=True)  # External grant ID (Chariot, etc.)
    daf_tracking_id = db.Column(db.String(255), nullable=True)  # Tracking ID for reconciliation

    # Amount fields (in cents)
    amount = db.Column(db.Integer, nullable=False)  # Gross amount in cents
    currency = db.Column(db.String(10), default='usd')
    stripe_fee = db.Column(db.Integer, nullable=True)  # Actual fee in cents
    stripe_fee_details = db.Column(db.JSON, nullable=True)  # Itemized breakdown
    net_amount = db.Column(db.Integer, nullable=True)  # Net after fees in cents
    
    # Payment method
    payment_method_type = db.Column(db.String(50), nullable=True)  # card/us_bank_account
    payment_method_last4 = db.Column(db.String(4), nullable=True)
    payment_method_brand = db.Column(db.String(50), nullable=True)  # visa/mastercard/amex
    bank_name = db.Column(db.String(255), nullable=True)  # For ACH
    
    # Donor message / dedication
    donor_comment = db.Column(db.Text, nullable=True)  # Comments, dedication, or message from donor

    # Status and type
    status = db.Column(db.String(20), default='pending')  # pending/succeeded/failed/refunded
    donation_type = db.Column(db.String(20), default='one_time')  # one_time/recurring
    source = db.Column(db.String(50), nullable=True)  # phone/email_link/direct/campaign_page

    # Charity / fund / designation — denormalized free-text label of which
    # cause this donation was directed to (e.g. "מתת מרדכי", "השריפה...",
    # "החתונה של נותי ושרה"). Populated from Nedarim's `Groupe` field for
    # nedarim donations, NULL for processors that don't tag.
    charity = db.Column(db.String(200), nullable=True, index=True)
    
    # Receipt
    receipt_number = db.Column(db.String(50), nullable=True)
    receipt_sent = db.Column(db.Boolean, default=False)
    receipt_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Refund fields
    refund_amount = db.Column(db.Integer, nullable=True)  # In cents
    refund_date = db.Column(db.DateTime, nullable=True)
    fee_refunded = db.Column(db.Integer, nullable=True)  # Usually $0
    fee_lost_on_refund = db.Column(db.Integer, nullable=True)  # stripe_fee - fee_refunded
    
    # Soft delete and timestamps
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    
    # === ZTORM FIELDS ===
    ztorm_truma_id = db.Column(db.Integer, nullable=True, index=True)
    agreement_id = db.Column(db.Integer, nullable=True)
    department_id = db.Column(db.Integer, nullable=True)
    payment_method = db.Column(db.String(20), nullable=True)
    paid_nis = db.Column(db.Numeric(12, 2), default=0)
    paid_usd = db.Column(db.Numeric(12, 2), default=0)
    expected_nis = db.Column(db.Numeric(12, 2), default=0)
    expected_usd = db.Column(db.Numeric(12, 2), default=0)
    entry_date = db.Column(db.Date, nullable=True)
    first_payment_date = db.Column(db.Date, nullable=True)
    last_payment_date = db.Column(db.Date, nullable=True)
    last_paid_date = db.Column(db.Date, nullable=True)
    cancellation_date = db.Column(db.Date, nullable=True)
    cancellation_reason = db.Column(db.String(255), nullable=True)
    cancellation_code = db.Column(db.String(50), nullable=True)
    send_receipt = db.Column(db.Boolean, default=True)
    receipt_name_ztorm = db.Column(db.String(200), nullable=True)
    receipt_tz = db.Column(db.String(9), nullable=True)
    receipt_email = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    user_created = db.Column(db.String(50), nullable=True)

    # Relationships
    commission = db.relationship('Commission', backref='donation', uselist=False)
    receipt = db.relationship('Receipt', backref='donation', uselist=False)
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    @property
    def amount_dollars(self):
        return self.amount / 100 if self.amount else 0
    
    @property
    def net_amount_dollars(self):
        return self.net_amount / 100 if self.net_amount else 0
    
    @property
    def stripe_fee_dollars(self):
        return self.stripe_fee / 100 if self.stripe_fee else 0
    
    @classmethod
    def query_active(cls):
        return cls.query.filter(cls.deleted_at.is_(None))
    
    def __repr__(self):
        return f'<Donation {self.id} ${self.amount_dollars}>'
