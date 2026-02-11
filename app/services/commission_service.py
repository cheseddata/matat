from decimal import Decimal
from ..models.user import User
from ..models.campaign import Campaign
from ..models.config_settings import ConfigSettings
from ..models.commission import Commission
from ..extensions import db


def compute_commission(amount_cents, commission_type, rate):
    """Compute commission amount in cents."""
    if commission_type == 'flat':
        # Rate is flat dollar amount, convert to cents
        return int(Decimal(str(rate)) * 100)
    elif commission_type == 'percentage':
        # Rate is percentage
        return int(amount_cents * Decimal(str(rate)) / 100)
    return 0


def calculate_commission(donation):
    """
    Calculate commission using the 4-level hierarchy:
    1. Campaign override rate
    2. Salesperson custom rate
    3. System-wide default rate
    4. No commission
    """
    amount = donation.amount  # Already in cents
    commission_type = None
    commission_rate = None
    
    # 1. Check campaign override
    if donation.campaign_id:
        campaign = Campaign.query.get(donation.campaign_id)
        if campaign and campaign.commission_override_type and campaign.commission_override_rate:
            commission_type = campaign.commission_override_type
            commission_rate = campaign.commission_override_rate
    
    # 2. Check salesperson custom rate
    if not commission_type and donation.salesperson_id:
        salesperson = User.query.get(donation.salesperson_id)
        if salesperson and salesperson.commission_type and salesperson.commission_rate:
            commission_type = salesperson.commission_type
            commission_rate = salesperson.commission_rate
    
    # 3. System default
    if not commission_type:
        config = ConfigSettings.query.first()
        if config and config.default_commission_type and config.default_commission_rate:
            commission_type = config.default_commission_type
            commission_rate = config.default_commission_rate
    
    # 4. No commission
    if not commission_type or not commission_rate:
        return None
    
    # Only create commission if there's a salesperson
    if not donation.salesperson_id:
        return None
    
    commission_amount = compute_commission(amount, commission_type, commission_rate)
    
    return {
        'commission_type': commission_type,
        'commission_rate': float(commission_rate),
        'commission_amount': commission_amount
    }


def create_commission_record(donation, commission_data):
    """Create a commission record for a donation."""
    if not commission_data or not donation.salesperson_id:
        return None
    
    commission = Commission(
        donation_id=donation.id,
        salesperson_id=donation.salesperson_id,
        donation_amount=donation.amount,
        commission_type=commission_data['commission_type'],
        commission_rate=commission_data['commission_rate'],
        commission_amount=commission_data['commission_amount'],
        status='pending'
    )
    db.session.add(commission)
    db.session.commit()
    return commission
