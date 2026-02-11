import shortuuid
from urllib.parse import urlencode
import os
from ..extensions import db
from ..models.donation_link import DonationLink
from ..models.user import User
from ..models.campaign import Campaign
from ..models.config_settings import ConfigSettings


def generate_short_code():
    """Generate a unique 8-char short code."""
    while True:
        code = shortuuid.uuid()[:8]
        existing = DonationLink.query.filter_by(short_code=code).first()
        if not existing:
            return code


def get_site_url():
    """Get site URL from config or environment."""
    config = ConfigSettings.query.first()
    if config and config.site_url:
        return config.site_url.rstrip('/')
    return os.environ.get('APP_DOMAIN', 'https://matatmordechai.org').rstrip('/')


def build_donation_url(short_code=None, ref_code=None, aff_code=None,
                       preset_amount=None, donor_name=None, donor_email=None,
                       donor_address=None, lang=None, donation_type=None):
    """Build a donation URL with parameters."""
    base_url = get_site_url()
    
    params = {}
    if ref_code:
        params['ref'] = ref_code
    if aff_code:
        params['aff'] = aff_code
    if preset_amount:
        params['amt'] = preset_amount
    if donor_name:
        params['name'] = donor_name
    if donor_email:
        params['email'] = donor_email
    if donor_address:
        params['addr'] = donor_address
    if lang:
        params['lang'] = lang
    if donation_type:
        params['type'] = donation_type
    
    if short_code:
        url = f"{base_url}/d/{short_code}"
        if params:
            url += '?' + urlencode(params)
    else:
        url = f"{base_url}/donate"
        if params:
            url += '?' + urlencode(params)
    
    return url


def create_donation_link(salesperson_id=None, campaign_id=None, 
                         donor_email=None, donor_name=None, donor_address=None,
                         preset_amount=None, preset_type=None):
    """Create a new donation link."""
    short_code = generate_short_code()
    
    # Get ref_code from salesperson
    ref_code = None
    if salesperson_id:
        salesperson = User.query.get(salesperson_id)
        if salesperson:
            ref_code = salesperson.ref_code
    
    # Get aff_code from campaign
    aff_code = None
    if campaign_id:
        campaign = Campaign.query.get(campaign_id)
        if campaign:
            aff_code = campaign.aff_code
    
    # Convert preset_amount to cents if provided as dollars
    preset_amount_cents = None
    if preset_amount:
        preset_amount_cents = int(float(preset_amount) * 100)
    
    # Build full URL
    full_url = build_donation_url(
        short_code=short_code,
        ref_code=ref_code,
        aff_code=aff_code,
        preset_amount=preset_amount,
        donor_name=donor_name,
        donor_email=donor_email,
        donor_address=donor_address
    )
    
    link = DonationLink(
        short_code=short_code,
        salesperson_id=salesperson_id,
        campaign_id=campaign_id,
        donor_email=donor_email,
        donor_name=donor_name,
        donor_address=donor_address,
        preset_amount=preset_amount_cents,
        preset_type=preset_type,
        full_url=full_url
    )
    db.session.add(link)
    db.session.commit()
    
    return link


def resolve_link(short_code):
    """Resolve a short code to its link data."""
    link = DonationLink.query.filter_by(short_code=short_code).first()
    if not link:
        return None
    
    data = {
        'link': link,
        'salesperson': None,
        'campaign': None,
        'ref_code': None,
        'aff_code': None
    }
    
    if link.salesperson_id:
        salesperson = User.query.get(link.salesperson_id)
        if salesperson:
            data['salesperson'] = salesperson
            data['ref_code'] = salesperson.ref_code
    
    if link.campaign_id:
        campaign = Campaign.query.get(link.campaign_id)
        if campaign:
            data['campaign'] = campaign
            data['aff_code'] = campaign.aff_code
    
    return data


def resolve_ref_code(ref_code):
    """Resolve a ref code to a salesperson."""
    if not ref_code:
        return None
    return User.query_active().filter_by(ref_code=ref_code, role='salesperson').first()


def resolve_aff_code(aff_code):
    """Resolve an aff code to a campaign."""
    if not aff_code:
        return None
    return Campaign.query.filter_by(aff_code=aff_code, is_active=True).first()
