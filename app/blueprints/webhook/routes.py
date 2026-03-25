import os
import logging
from flask import request, jsonify, current_app
from . import webhook_bp
from ...extensions import csrf, db
from ...models.donation import Donation
from ...models.donor import Donor
from ...models.donation_link import DonationLink
from ...models.campaign import Campaign
from ...services.stripe_service import construct_webhook_event, retrieve_balance_transaction, get_stripe_keys, is_test_mode
from ...services.commission_service import calculate_commission, create_commission_record
from ...services.receipt_service import create_receipt_atomic
from ...services.email_service import send_receipt_email

logger = logging.getLogger(__name__)


@webhook_bp.route('/stripe/webhook', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    logger.info('Stripe webhook received')
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    logger.info(f'Webhook signature present: {bool(sig_header)}')

    # Get webhook secret from database (falls back to env var)
    _, _, mode, webhook_secret = get_stripe_keys()
    logger.info(f'Webhook mode: {mode}, secret configured: {bool(webhook_secret and webhook_secret != "whsec_placeholder")}')

    if not webhook_secret or webhook_secret == 'whsec_placeholder':
        # In dev mode without webhook secret, just acknowledge
        logger.warning('Webhook received but no secret configured (dev mode)')
        return jsonify({'status': 'received (dev mode)'}), 200

    try:
        event = construct_webhook_event(payload, sig_header, webhook_secret)
        logger.info(f'Webhook event verified: {event["type"]}')
    except Exception as e:
        logger.error(f'Webhook signature verification failed: {str(e)}')
        return jsonify({'error': str(e)}), 400

    event_type = event['type']
    data = event['data']['object']
    logger.info(f'Processing webhook event: {event_type}')

    if event_type == 'payment_intent.succeeded':
        logger.info(f'Handling payment_intent.succeeded: {data.get("id")}')
        handle_payment_intent_succeeded(data)
    elif event_type == 'charge.succeeded':
        logger.info(f'Handling charge.succeeded: {data.get("id")}')
        handle_charge_succeeded(data)
    elif event_type == 'charge.refunded':
        logger.info(f'Handling charge.refunded: {data.get("id")}')
        handle_charge_refunded(data)
    elif event_type == 'charge.failed':
        logger.info(f'Handling charge.failed: {data.get("id")}')
        handle_charge_failed(data)
    elif event_type == 'invoice.paid':
        logger.info(f'Handling invoice.paid: {data.get("id")}')
        handle_invoice_paid(data)
    else:
        logger.info(f'Unhandled webhook event type: {event_type}')

    logger.info(f'Webhook {event_type} processed successfully')
    return jsonify({'status': 'received'}), 200


def handle_payment_intent_succeeded(pi):
    """Handle successful payment intent."""
    # Check for duplicate (idempotency)
    existing = Donation.query.filter_by(stripe_payment_intent_id=pi['id']).first()
    if existing:
        return  # Already processed
    
    metadata = pi.get('metadata', {})
    
    # Get or create donor
    donor_id = metadata.get('donor_id')
    donor = Donor.query.get(donor_id) if donor_id else None
    
    if not donor:
        # Create donor from metadata if not exists
        donor = Donor(
            first_name=metadata.get('donor_first_name', 'Unknown'),
            last_name=metadata.get('donor_last_name', 'Donor'),
            email=metadata.get('donor_email', 'unknown@example.com'),
            stripe_customer_id=pi.get('customer'),
            test=is_test_mode()
        )
        db.session.add(donor)
        db.session.flush()
    
    # Resolve salesperson from ref code
    salesperson_id = metadata.get('salesperson_id')
    
    # Resolve campaign from aff code
    campaign_id = metadata.get('campaign_id')
    
    # Resolve link
    link_id = metadata.get('link_id')
    
    # Create donation record
    donation = Donation(
        donor_id=donor.id,
        salesperson_id=int(salesperson_id) if salesperson_id else None,
        campaign_id=int(campaign_id) if campaign_id else None,
        link_id=int(link_id) if link_id else None,
        stripe_payment_intent_id=pi['id'],
        amount=pi['amount'],
        currency=pi.get('currency', 'usd'),
        status='succeeded',
        donation_type=metadata.get('donation_type', 'one_time'),
        source=metadata.get('source', 'direct'),
        stripe_metadata=metadata
    )
    db.session.add(donation)
    db.session.flush()
    
    # Calculate and create commission
    commission_data = calculate_commission(donation)
    if commission_data:
        create_commission_record(donation, commission_data)
    
    # Update campaign total if applicable
    if donation.campaign_id:
        campaign = Campaign.query.get(donation.campaign_id)
        if campaign:
            campaign.total_raised = (campaign.total_raised or 0) + donation.amount
    
    # Update link usage if applicable
    if donation.link_id:
        link = DonationLink.query.get(donation.link_id)
        if link:
            link.times_used = (link.times_used or 0) + 1
            from datetime import datetime
            link.last_used_at = datetime.utcnow()
    
    db.session.commit()


def handle_charge_succeeded(charge):
    """Handle successful charge - capture fee data and generate receipt."""
    pi_id = charge.get('payment_intent')
    if not pi_id:
        return

    donation = Donation.query.filter_by(stripe_payment_intent_id=pi_id).first()
    if not donation:
        return

    # Update with charge details
    donation.stripe_charge_id = charge['id']

    # Get payment method details
    pm_details = charge.get('payment_method_details', {})
    pm_type = pm_details.get('type')
    donation.payment_method_type = pm_type

    if pm_type == 'card':
        card = pm_details.get('card', {})
        donation.payment_method_last4 = card.get('last4')
        donation.payment_method_brand = card.get('brand')
    elif pm_type == 'us_bank_account':
        bank = pm_details.get('us_bank_account', {})
        donation.payment_method_last4 = bank.get('last4')
        donation.bank_name = bank.get('bank_name')

    donation.stripe_receipt_url = charge.get('receipt_url')

    # Retrieve balance transaction for fee data
    bt_id = charge.get('balance_transaction')
    if bt_id:
        try:
            bt_data = retrieve_balance_transaction(bt_id)
            donation.stripe_balance_transaction_id = bt_id
            donation.stripe_fee = bt_data['fee']
            donation.stripe_fee_details = bt_data['fee_details']
            donation.net_amount = bt_data['net']
        except Exception as e:
            logger.warning(f"Fee capture failed for charge {charge['id']}: {e}")

    # Generate receipt atomically (within this transaction)
    # Only generate if not already generated
    receipt = None
    donor = None
    if not donation.receipt_number:
        try:
            donor = Donor.query.get(donation.donor_id)
            if donor:
                receipt = create_receipt_atomic(donation, donor)
                logger.info(f"Receipt {receipt.receipt_number} generated for donation {donation.id}")
        except Exception as e:
            logger.error(f"Receipt generation failed for donation {donation.id}: {e}")
            # Don't fail the whole webhook - donation is still valid

    db.session.commit()

    # Send receipt email after transaction commits (outside transaction)
    if receipt and donor and donor.email:
        try:
            send_receipt_email(donor, donation, receipt)
            logger.info(f"Receipt email sent to {donor.email} for donation {donation.id}")
        except Exception as e:
            logger.error(f"Receipt email failed for donation {donation.id}: {e}")


def handle_charge_refunded(charge):
    """Handle refund - update status and track fee loss."""
    pi_id = charge.get('payment_intent')
    if not pi_id:
        return
    
    donation = Donation.query.filter_by(stripe_payment_intent_id=pi_id).first()
    if not donation:
        return
    
    from datetime import datetime
    
    donation.status = 'refunded'
    donation.refund_amount = charge.get('amount_refunded', 0)
    donation.refund_date = datetime.utcnow()
    
    # Stripe usually doesn't refund the fee
    donation.fee_refunded = 0
    donation.fee_lost_on_refund = donation.stripe_fee or 0
    
    # Void the commission
    if donation.commission:
        donation.commission.status = 'voided'
    
    # Update campaign total
    if donation.campaign_id:
        campaign = Campaign.query.get(donation.campaign_id)
        if campaign:
            campaign.total_raised = max(0, (campaign.total_raised or 0) - donation.refund_amount)
    
    db.session.commit()


def handle_charge_failed(charge):
    """Handle failed charge."""
    pi_id = charge.get('payment_intent')
    if not pi_id:
        return
    
    donation = Donation.query.filter_by(stripe_payment_intent_id=pi_id).first()
    if donation:
        donation.status = 'failed'
        db.session.commit()


def handle_invoice_paid(invoice):
    """Handle recurring payment invoice."""
    # Similar to payment_intent.succeeded but for subscriptions
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return

    # Check for existing donation with this invoice
    existing = Donation.query.filter_by(stripe_charge_id=invoice.get('charge')).first()
    if existing:
        return

    metadata = invoice.get('metadata', {})
    customer_id = invoice.get('customer')

    # Find donor by Stripe customer ID
    donor = Donor.query.filter_by(stripe_customer_id=customer_id).first()
    if not donor:
        return

    # Create donation record for this installment
    donation = Donation(
        donor_id=donor.id,
        salesperson_id=metadata.get('salesperson_id'),
        campaign_id=metadata.get('campaign_id'),
        stripe_charge_id=invoice.get('charge'),
        stripe_subscription_id=subscription_id,
        amount=invoice.get('amount_paid', 0),
        currency=invoice.get('currency', 'usd'),
        status='succeeded',
        donation_type='recurring',
        source=metadata.get('source', 'recurring'),
        stripe_metadata=metadata
    )
    db.session.add(donation)
    db.session.flush()

    # Calculate commission
    commission_data = calculate_commission(donation)
    if commission_data:
        create_commission_record(donation, commission_data)

    # Generate receipt for recurring payment
    receipt = None
    try:
        receipt = create_receipt_atomic(donation, donor)
        logger.info(f"Receipt {receipt.receipt_number} generated for recurring donation {donation.id}")
    except Exception as e:
        logger.error(f"Receipt generation failed for recurring donation {donation.id}: {e}")

    db.session.commit()

    # Send receipt email after transaction commits
    if receipt and donor.email:
        try:
            send_receipt_email(donor, donation, receipt)
            logger.info(f"Receipt email sent to {donor.email} for recurring donation {donation.id}")
        except Exception as e:
            logger.error(f"Receipt email failed for recurring donation {donation.id}: {e}")
