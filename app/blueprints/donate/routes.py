import os
import logging
from flask import render_template, request, jsonify, redirect, url_for
from . import donate_bp
from ...extensions import db, csrf
from ...models.donation import Donation
from ...models.donor import Donor
from ...models.donation_link import DonationLink
from ...models.payment_processor import PaymentProcessor
from ...services.link_service import resolve_link, resolve_ref_code, resolve_aff_code
from ...services.stripe_service import get_stripe_keys, create_payment_intent, get_or_create_customer, is_test_mode

logger = logging.getLogger(__name__)


def get_enabled_processors():
    """Get enabled payment processors grouped by type."""
    processors = PaymentProcessor.get_enabled()

    result = {
        'credit_card': [],
        'daf': [],
        'has_stripe': False,
        'has_daf': False,
        'has_donors_fund': False,
        'has_matbia': False,
        'has_chariot': False,
    }

    for p in processors:
        proc_type = p.processor_type or 'credit_card'

        if proc_type in ('daf', 'daf_aggregator'):
            result['daf'].append(p)
            result['has_daf'] = True
            if p.code == 'donors_fund':
                result['has_donors_fund'] = True
            elif p.code == 'matbia':
                result['has_matbia'] = True
            elif p.code == 'chariot':
                result['has_chariot'] = True
        else:
            result['credit_card'].append(p)
            if p.code == 'stripe':
                result['has_stripe'] = True

    return result


@donate_bp.route('/donate')
def donation_page():
    """Public donation page."""
    # Get URL parameters
    ref_code = request.args.get('ref')
    aff_code = request.args.get('aff')
    preset_amount = request.args.get('amt')
    donor_name = request.args.get('name', '')
    donor_email = request.args.get('email', '')
    donor_address = request.args.get('addr', '')
    lang = request.args.get('lang', 'en')
    donation_type = request.args.get('type', 'onetime')

    # Resolve salesperson and campaign
    salesperson = resolve_ref_code(ref_code) if ref_code else None
    campaign = resolve_aff_code(aff_code) if aff_code else None

    _, publishable_key, stripe_mode, _ = get_stripe_keys()

    # Get enabled payment processors
    processors = get_enabled_processors()

    # Get Chariot connect_id if enabled
    chariot_connect_id = None
    if processors['has_chariot']:
        chariot_proc = PaymentProcessor.get_by_code('chariot')
        if chariot_proc and chariot_proc.config_json:
            chariot_connect_id = chariot_proc.config_json.get('connect_id')

    return render_template(
        'donate/donation_page.html',
        ref_code=ref_code,
        aff_code=aff_code,
        preset_amount=preset_amount,
        donor_name=donor_name,
        donor_email=donor_email,
        donor_address=donor_address,
        salesperson=salesperson,
        campaign=campaign,
        stripe_publishable_key=publishable_key,
        stripe_mode=stripe_mode,
        donation_type=donation_type,
        lang=lang,
        # Payment processor flags
        processors=processors,
        chariot_connect_id=chariot_connect_id,
    )


@donate_bp.route('/d/<short_code>')
def resolve_short_link(short_code):
    """Resolve short link and redirect to donation page with usage tracking."""
    from datetime import datetime

    link_data = resolve_link(short_code)

    if not link_data:
        return render_template('donate/link_not_found.html'), 404

    link = link_data['link']

    # Track link visit (usage tracking)
    link.times_used = (link.times_used or 0) + 1
    link.last_used_at = datetime.utcnow()
    db.session.commit()

    # Build redirect URL with parameters
    params = {}
    if link_data['ref_code']:
        params['ref'] = link_data['ref_code']
    if link_data['aff_code']:
        params['aff'] = link_data['aff_code']
    if link.preset_amount:
        params['amt'] = link.preset_amount_dollars
    if link.donor_name:
        params['name'] = link.donor_name
    if link.donor_email:
        params['email'] = link.donor_email
    if link.donor_address:
        params['addr'] = link.donor_address
    if link.preset_type:
        params['type'] = link.preset_type

    # Add link_id for tracking donations back to link
    params['link_id'] = link.id

    return redirect(url_for('donate.donation_page', **params))


@donate_bp.route('/donate/create-payment-intent', methods=['POST'])
def create_payment_intent_route():
    """Create a Stripe PaymentIntent."""
    data = request.get_json()

    amount_dollars = float(data.get('amount', 0))
    if amount_dollars <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    amount_cents = int(amount_dollars * 100)

    # Get or create donor
    donor = Donor.query.filter_by(email=data.get('email')).first()
    if not donor:
        donor = Donor(
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=data.get('email'),
            phone=data.get('phone'),
            address_line1=data.get('address_line1'),
            address_line2=data.get('address_line2'),
            city=data.get('city'),
            state=data.get('state'),
            zip=data.get('zip'),
            country=data.get('country', 'US'),
            language_pref=data.get('language', 'en'),
            test=is_test_mode()
        )
        db.session.add(donor)
        db.session.flush()
    else:
        # Update donor info if provided
        if data.get('first_name'):
            donor.first_name = data.get('first_name')
        if data.get('last_name'):
            donor.last_name = data.get('last_name')
        if data.get('address_line1'):
            donor.address_line1 = data.get('address_line1')
        if data.get('phone'):
            donor.phone = data.get('phone')
        if data.get('language'):
            donor.language_pref = data.get('language')

    db.session.commit()
    
    # Get Stripe customer
    customer_id = get_or_create_customer(donor)
    
    # Resolve salesperson and campaign
    salesperson_id = None
    campaign_id = None
    
    ref_code = data.get('ref_code')
    if ref_code:
        salesperson = resolve_ref_code(ref_code)
        if salesperson:
            salesperson_id = salesperson.id
    
    aff_code = data.get('aff_code')
    if aff_code:
        campaign = resolve_aff_code(aff_code)
        if campaign:
            campaign_id = campaign.id
    
    # Build metadata
    metadata = {
        'donor_id': str(donor.id),
        'donor_email': donor.email,
        'donor_first_name': donor.first_name,
        'donor_last_name': donor.last_name,
        'donation_type': data.get('donation_type', 'one_time'),
        'source': data.get('source', 'direct')
    }
    
    if salesperson_id:
        metadata['salesperson_id'] = str(salesperson_id)
        metadata['ref_code'] = ref_code
    
    if campaign_id:
        metadata['campaign_id'] = str(campaign_id)
        metadata['aff_code'] = aff_code
    
    link_id = data.get('link_id')
    if link_id:
        metadata['link_id'] = str(link_id)
    
    try:
        intent = create_payment_intent(
            amount_cents=amount_cents,
            currency='usd',
            customer_id=customer_id,
            metadata=metadata
        )
        
        return jsonify({
            'clientSecret': intent.client_secret,
            'paymentIntentId': intent.id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@donate_bp.route('/donate/success')
def donation_success():
    """Success page after donation."""
    payment_intent_id = request.args.get('payment_intent')
    daf_confirmation = request.args.get('daf_confirmation')
    daf_provider = request.args.get('daf_provider')

    return render_template(
        'donate/success.html',
        payment_intent_id=payment_intent_id,
        daf_confirmation=daf_confirmation,
        daf_provider=daf_provider
    )


# =============================================================================
# DAF PAYMENT ROUTES
# =============================================================================

@donate_bp.route('/donate/process-donors-fund', methods=['POST'])
def process_donors_fund():
    """Process a donation via The Donors Fund."""
    from ...services.payment.donorsfund_processor import DonorsFundProcessor
    from ...services.commission_service import calculate_commission, create_commission_record

    data = request.get_json()

    # Validate amount
    amount_dollars = float(data.get('amount', 0))
    if amount_dollars <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    amount_cents = int(amount_dollars * 100)

    # Get processor config
    processor_db = PaymentProcessor.get_by_code('donors_fund')
    if not processor_db or not processor_db.enabled:
        return jsonify({'error': 'Donors Fund not enabled'}), 400

    config = processor_db.config_json or {}
    processor = DonorsFundProcessor(config=config)

    if not processor.initialize():
        return jsonify({'error': 'Donors Fund not configured'}), 400

    # Get or create donor
    donor = Donor.query.filter_by(email=data.get('email')).first()
    if not donor:
        donor = Donor(
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=data.get('email'),
            phone=data.get('phone'),
            country=data.get('country', 'US'),
            test=False  # DAF donations are always real
        )
        db.session.add(donor)
        db.session.flush()

    # Build metadata for payment
    metadata = {
        'purpose': data.get('purpose', ''),
        'purpose_note': data.get('purpose_note', ''),
    }

    # Auth method: username+pin OR card+cvv
    if data.get('auth_method') == 'username':
        metadata['username'] = data.get('username')
        metadata['pin'] = data.get('pin')
    else:
        metadata['card_number'] = data.get('card_number')
        metadata['cvv'] = data.get('cvv')

    # Process payment
    result = processor.create_payment(
        amount_cents=amount_cents,
        currency='USD',
        donor_email=donor.email,
        donor_name=f"{donor.first_name} {donor.last_name}",
        metadata=metadata
    )

    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Payment failed')}), 400

    # Resolve salesperson and campaign
    salesperson_id = None
    campaign_id = None

    ref_code = data.get('ref_code')
    if ref_code:
        salesperson = resolve_ref_code(ref_code)
        if salesperson:
            salesperson_id = salesperson.id

    aff_code = data.get('aff_code')
    if aff_code:
        campaign = resolve_aff_code(aff_code)
        if campaign:
            campaign_id = campaign.id

    # Create donation record
    donation = Donation(
        donor_id=donor.id,
        salesperson_id=salesperson_id,
        campaign_id=campaign_id,
        link_id=data.get('link_id'),
        payment_processor='donors_fund',
        processor_transaction_id=result.get('transaction_id'),
        processor_confirmation=result.get('confirmation_number'),
        is_daf_donation=True,
        daf_provider='The Donors Fund',
        amount=amount_cents,
        currency='USD',
        status='succeeded',
        donation_type='one_time',
        source=data.get('source', 'direct'),
    )
    db.session.add(donation)
    db.session.flush()

    # Calculate commission
    commission_data = calculate_commission(donation)
    if commission_data:
        create_commission_record(donation, commission_data)

    db.session.commit()

    logger.info(f'[donors_fund] Created donation {donation.id}: ${amount_dollars}')

    return jsonify({
        'success': True,
        'confirmation': result.get('confirmation_number'),
        'donation_id': donation.id
    })


@donate_bp.route('/donate/process-matbia', methods=['POST'])
def process_matbia():
    """Process a donation via Matbia charity card."""
    from ...services.payment.matbia_processor import MatbiaProcessor
    from ...services.commission_service import calculate_commission, create_commission_record

    data = request.get_json()

    # Validate amount
    amount_dollars = float(data.get('amount', 0))
    if amount_dollars <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    amount_cents = int(amount_dollars * 100)

    # Validate card number
    card_number = data.get('card_number', '').strip()
    if not card_number:
        return jsonify({'error': 'Matbia card number required'}), 400

    # Get processor config
    processor_db = PaymentProcessor.get_by_code('matbia')
    if not processor_db or not processor_db.enabled:
        return jsonify({'error': 'Matbia not enabled'}), 400

    config = processor_db.config_json or {}
    processor = MatbiaProcessor(config=config)

    if not processor.initialize():
        return jsonify({'error': 'Matbia not configured'}), 400

    # Get or create donor
    donor = Donor.query.filter_by(email=data.get('email')).first()
    if not donor:
        donor = Donor(
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=data.get('email'),
            phone=data.get('phone'),
            country=data.get('country', 'US'),
            test=False  # Matbia donations are always real
        )
        db.session.add(donor)
        db.session.flush()

    # Process payment
    result = processor.create_payment(
        amount_cents=amount_cents,
        currency='USD',
        donor_email=donor.email,
        donor_name=f"{donor.first_name} {donor.last_name}",
        metadata={
            'card_number': card_number,
            'note': data.get('note', ''),
        }
    )

    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Payment failed')}), 400

    # Resolve salesperson and campaign
    salesperson_id = None
    campaign_id = None

    ref_code = data.get('ref_code')
    if ref_code:
        salesperson = resolve_ref_code(ref_code)
        if salesperson:
            salesperson_id = salesperson.id

    aff_code = data.get('aff_code')
    if aff_code:
        campaign = resolve_aff_code(aff_code)
        if campaign:
            campaign_id = campaign.id

    # Create donation record
    donation = Donation(
        donor_id=donor.id,
        salesperson_id=salesperson_id,
        campaign_id=campaign_id,
        link_id=data.get('link_id'),
        payment_processor='matbia',
        processor_transaction_id=result.get('transaction_id'),
        processor_confirmation=result.get('confirmation_number'),
        is_daf_donation=True,
        daf_provider='Matbia',
        amount=amount_cents,
        currency='USD',
        status='succeeded',
        donation_type='one_time',
        source=data.get('source', 'direct'),
    )
    db.session.add(donation)
    db.session.flush()

    # Calculate commission
    commission_data = calculate_commission(donation)
    if commission_data:
        create_commission_record(donation, commission_data)

    db.session.commit()

    logger.info(f'[matbia] Created donation {donation.id}: ${amount_dollars}')

    return jsonify({
        'success': True,
        'confirmation': result.get('confirmation_number'),
        'donation_id': donation.id
    })


@donate_bp.route('/donate/validate-donors-fund-card', methods=['POST'])
def validate_donors_fund_card():
    """Pre-validate a Donors Fund giving card."""
    from ...services.payment.donorsfund_processor import DonorsFundProcessor

    data = request.get_json()

    processor_db = PaymentProcessor.get_by_code('donors_fund')
    if not processor_db or not processor_db.enabled:
        return jsonify({'error': 'Donors Fund not enabled'}), 400

    config = processor_db.config_json or {}
    processor = DonorsFundProcessor(config=config)

    if not processor.initialize():
        return jsonify({'error': 'Donors Fund not configured'}), 400

    result = processor.validate_card(
        card_number=data.get('card_number', ''),
        cvv=data.get('cvv', '')
    )

    return jsonify(result)


@donate_bp.route('/api/donation/status')
def donation_status():
    """Check donation status for polling."""
    pi_id = request.args.get('pi')
    if not pi_id:
        return jsonify({'found': False})
    
    donation = Donation.query.filter_by(stripe_payment_intent_id=pi_id).first()
    
    if donation:
        return jsonify({
            'found': True,
            'status': donation.status,
            'receipt_number': donation.receipt_number,
            'amount': donation.amount_dollars
        })
    
    return jsonify({'found': False})
