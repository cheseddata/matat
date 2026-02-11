from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from sqlalchemy import func
from datetime import datetime, timedelta
from . import salesperson_bp
from ...extensions import db
from ...utils.decorators import salesperson_required
from ...models.donation import Donation
from ...models.commission import Commission
from ...models.donation_link import DonationLink
from ...models.donor import Donor
from ...services.link_service import create_donation_link
from ...services.email_service import send_donation_link_email, send_donation_link_sms
from ...services.stripe_service import get_stripe_keys, create_payment_intent, get_or_create_customer, is_test_mode


@salesperson_bp.route('/dashboard')
@salesperson_required
def dashboard():
    """Salesperson dashboard with stats."""
    # All queries strictly scoped to current_user.id
    salesperson_id = current_user.id

    # Get donation stats
    total_donations = db.session.query(func.sum(Donation.amount)).filter(
        Donation.salesperson_id == salesperson_id,
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).scalar() or 0

    donation_count = Donation.query.filter(
        Donation.salesperson_id == salesperson_id,
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).count()

    # Get commission stats
    total_commissions = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.salesperson_id == salesperson_id
    ).scalar() or 0

    pending_commissions = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.salesperson_id == salesperson_id,
        Commission.status == 'pending'
    ).scalar() or 0

    paid_commissions = db.session.query(func.sum(Commission.commission_amount)).filter(
        Commission.salesperson_id == salesperson_id,
        Commission.status == 'paid'
    ).scalar() or 0

    # Get link stats
    link_count = DonationLink.query.filter(
        DonationLink.salesperson_id == salesperson_id
    ).count()

    # Recent donations (last 10)
    recent_donations = Donation.query.filter(
        Donation.salesperson_id == salesperson_id,
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None)
    ).order_by(Donation.created_at.desc()).limit(10).all()

    # This month's stats
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_donations = db.session.query(func.sum(Donation.amount)).filter(
        Donation.salesperson_id == salesperson_id,
        Donation.status == 'succeeded',
        Donation.deleted_at.is_(None),
        Donation.created_at >= month_start
    ).scalar() or 0

    return render_template(
        'salesperson/dashboard.html',
        total_donations=total_donations / 100,
        donation_count=donation_count,
        total_commissions=total_commissions / 100,
        pending_commissions=pending_commissions / 100,
        paid_commissions=paid_commissions / 100,
        link_count=link_count,
        recent_donations=recent_donations,
        this_month_donations=this_month_donations / 100,
        ref_code=current_user.ref_code
    )


@salesperson_bp.route('/send-link', methods=['GET', 'POST'])
@salesperson_required
def send_link():
    """Send donation link form."""
    if request.method == 'POST':
        donor_email = request.form.get('donor_email', '').strip()
        donor_name = request.form.get('donor_name', '').strip()
        donor_address = request.form.get('donor_address', '').strip()
        preset_amount = request.form.get('preset_amount', '').strip()
        preset_type = request.form.get('preset_type', 'onetime')
        language = request.form.get('language', 'en')
        campaign_id = request.form.get('campaign_id')

        if not donor_email:
            flash('Email address is required.', 'error')
            return redirect(url_for('salesperson.send_link'))

        # Create donation link scoped to current salesperson
        link = create_donation_link(
            salesperson_id=current_user.id,
            campaign_id=int(campaign_id) if campaign_id else None,
            donor_email=donor_email,
            donor_name=donor_name,
            donor_address=donor_address,
            preset_amount=preset_amount if preset_amount else None,
            preset_type=preset_type
        )

        # Send the email
        success = send_donation_link_email(
            donor_email=donor_email,
            donor_name=donor_name,
            link=link,
            salesperson=current_user,
            language=language
        )

        if success:
            flash(f'Donation link sent successfully to {donor_email}!', 'success')
        else:
            flash(f'Link created but email delivery failed. Link: {link.full_url}', 'warning')

        return redirect(url_for('salesperson.my_links'))

    # Get available campaigns for dropdown
    from ...models.campaign import Campaign
    campaigns = Campaign.query.filter_by(is_active=True).all()

    return render_template(
        'salesperson/send_link.html',
        campaigns=campaigns
    )


@salesperson_bp.route('/phone-entry', methods=['GET', 'POST'])
@salesperson_required
def phone_entry():
    """Phone entry form for taking donations over the phone."""
    _, publishable_key, stripe_mode, _ = get_stripe_keys()

    if request.method == 'POST':
        # Handle JSON API request for creating payment intent
        if request.is_json:
            data = request.get_json()
            return _create_phone_payment_intent(data)

        # Handle form submission for sending link via SMS
        phone = request.form.get('phone', '').strip()
        donor_name = request.form.get('donor_name', '').strip()
        preset_amount = request.form.get('preset_amount', '').strip()
        language = request.form.get('language', 'en')

        if not phone:
            flash('Phone number is required.', 'error')
            return redirect(url_for('salesperson.phone_entry'))

        # Create donation link
        link = create_donation_link(
            salesperson_id=current_user.id,
            donor_name=donor_name,
            preset_amount=preset_amount if preset_amount else None,
            preset_type='onetime'
        )

        # Send SMS
        success = send_donation_link_sms(
            phone=phone,
            donor_name=donor_name,
            link=link,
            salesperson=current_user,
            language=language
        )

        if success:
            flash(f'Link sent via SMS to {phone}!', 'success')
        else:
            flash(f'SMS delivery not configured. Link: {link.full_url}', 'warning')

        return redirect(url_for('salesperson.phone_entry'))

    return render_template(
        'salesperson/phone_entry.html',
        stripe_publishable_key=publishable_key,
        stripe_mode=stripe_mode
    )


def _create_phone_payment_intent(data):
    """Create payment intent for phone donations."""
    try:
        amount_dollars = float(data.get('amount', 0))
        if amount_dollars <= 0:
            return jsonify({'error': 'Invalid amount'}), 400

        amount_cents = int(amount_dollars * 100)

        # Validate email
        email = data.get('email', '').strip()
        if not email:
            return jsonify({'error': 'Email is required'}), 400

        # Get or create donor
        donor = Donor.query.filter_by(email=email).first()
        if not donor:
            donor = Donor(
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                email=email,
                phone=data.get('phone'),
                address_line1=data.get('address_line1'),
                city=data.get('city'),
                state=data.get('state'),
                zip=data.get('zip'),
                country=data.get('country', 'US'),
                test=is_test_mode()
            )
            db.session.add(donor)
            db.session.flush()

        db.session.commit()

        # Get Stripe customer
        customer_id = get_or_create_customer(donor)

        # Build metadata - scoped to current salesperson
        metadata = {
            'donor_id': str(donor.id),
            'donor_email': donor.email,
            'donor_first_name': donor.first_name,
            'donor_last_name': donor.last_name,
            'donation_type': 'one_time',
            'source': 'phone',
            'salesperson_id': str(current_user.id),
            'ref_code': current_user.ref_code or ''
        }

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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400


@salesperson_bp.route('/my-links')
@salesperson_required
def my_links():
    """View all links created by this salesperson."""
    # Strictly scoped to current user
    links = DonationLink.query.filter(
        DonationLink.salesperson_id == current_user.id
    ).order_by(DonationLink.created_at.desc()).all()

    return render_template(
        'salesperson/my_links.html',
        links=links
    )


@salesperson_bp.route('/my-commissions')
@salesperson_required
def my_commissions():
    """View commission history."""
    # Strictly scoped to current user
    commissions = Commission.query.filter(
        Commission.salesperson_id == current_user.id
    ).order_by(Commission.created_at.desc()).all()

    # Calculate totals
    total_pending = sum(c.commission_amount for c in commissions if c.status == 'pending') / 100
    total_paid = sum(c.commission_amount for c in commissions if c.status == 'paid') / 100
    total_voided = sum(c.commission_amount for c in commissions if c.status == 'voided') / 100

    return render_template(
        'salesperson/my_commissions.html',
        commissions=commissions,
        total_pending=total_pending,
        total_paid=total_paid,
        total_voided=total_voided
    )


@salesperson_bp.route('/my-donations')
@salesperson_required
def my_donations():
    """View all donations attributed to this salesperson."""
    # Strictly scoped to current user
    donations = Donation.query.filter(
        Donation.salesperson_id == current_user.id,
        Donation.deleted_at.is_(None)
    ).order_by(Donation.created_at.desc()).all()

    return render_template(
        'salesperson/my_donations.html',
        donations=donations
    )


@salesperson_bp.route('/api/quick-link', methods=['POST'])
@salesperson_required
def quick_link():
    """API to quickly generate a shareable link."""
    data = request.get_json() or {}

    link = create_donation_link(
        salesperson_id=current_user.id,
        preset_amount=data.get('amount'),
        preset_type=data.get('type', 'onetime')
    )

    return jsonify({
        'success': True,
        'short_code': link.short_code,
        'full_url': link.full_url
    })


@salesperson_bp.route('/api/create-payment-intent', methods=['POST'])
@salesperson_required
def create_payment_intent_api():
    """API to create a payment intent for phone donations."""
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400

    data = request.get_json()
    return _create_phone_payment_intent(data)
