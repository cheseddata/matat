import os
import stripe
from ..models.config_settings import ConfigSettings

def get_stripe_keys():
    """Get Stripe keys from database config, fallback to env vars."""
    config = ConfigSettings.query.first()
    mode = config.stripe_mode if config else os.environ.get('STRIPE_MODE', 'test')

    if mode == 'live':
        secret = (config.stripe_live_secret_key if config and config.stripe_live_secret_key
                  else os.environ.get('STRIPE_LIVE_SECRET_KEY'))
        publishable = (config.stripe_live_publishable_key if config and config.stripe_live_publishable_key
                       else os.environ.get('STRIPE_LIVE_PUBLISHABLE_KEY'))
    else:
        secret = (config.stripe_test_secret_key if config and config.stripe_test_secret_key
                  else os.environ.get('STRIPE_TEST_SECRET_KEY'))
        publishable = (config.stripe_test_publishable_key if config and config.stripe_test_publishable_key
                       else os.environ.get('STRIPE_TEST_PUBLISHABLE_KEY'))

    webhook_secret = (config.stripe_webhook_secret if config and config.stripe_webhook_secret
                      else os.environ.get('STRIPE_WEBHOOK_SECRET'))

    return secret, publishable, mode, webhook_secret

def init_stripe():
    """Initialize Stripe with the appropriate key."""
    secret, _, _, _ = get_stripe_keys()
    stripe.api_key = secret
    return stripe

def retrieve_balance_transaction(bt_id):
    """Retrieve balance transaction for fee data."""
    s = init_stripe()
    bt = s.BalanceTransaction.retrieve(bt_id)
    return {
        'fee': bt.fee,
        'fee_details': [{'type': fd.type, 'amount': fd.amount, 'description': fd.description} for fd in bt.fee_details],
        'net': bt.net
    }

def create_customer(email, name, metadata=None):
    """Create a Stripe customer."""
    s = init_stripe()
    return s.Customer.create(
        email=email,
        name=name,
        metadata=metadata or {}
    )

def get_or_create_customer(donor):
    """Get existing Stripe customer or create new one."""
    from ..extensions import db
    
    if donor.stripe_customer_id:
        return donor.stripe_customer_id
    
    customer = create_customer(
        email=donor.email,
        name=donor.full_name,
        metadata={'donor_id': donor.id}
    )
    donor.stripe_customer_id = customer.id
    db.session.commit()
    return customer.id

def create_payment_intent(amount_cents, currency, customer_id, metadata=None):
    """Create a Stripe PaymentIntent."""
    s = init_stripe()
    return s.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        customer=customer_id,
        metadata=metadata or {},
        automatic_payment_methods={'enabled': True}
    )

def construct_webhook_event(payload, sig_header, webhook_secret):
    """Construct and verify a webhook event."""
    s = init_stripe()
    return s.Webhook.construct_event(payload, sig_header, webhook_secret)

def is_test_mode():
    """Check if Stripe is in test mode."""
    _, _, mode, _ = get_stripe_keys()
    return mode == 'test'
