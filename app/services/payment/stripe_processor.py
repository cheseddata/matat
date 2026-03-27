"""
Stripe payment processor implementation.

Wraps existing stripe_service functions with the BasePaymentProcessor interface.
"""
import os
import logging
import stripe
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor
from ...models.config_settings import ConfigSettings

logger = logging.getLogger(__name__)


class StripeProcessor(BasePaymentProcessor):
    """
    Stripe payment processor.

    Handles credit card payments via Stripe Elements.
    Supports USD and most international currencies.
    """

    SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'ILS']

    @property
    def code(self) -> str:
        return 'stripe'

    @property
    def display_name(self) -> str:
        return 'Credit Card'

    def initialize(self) -> bool:
        """Initialize Stripe with API keys."""
        try:
            secret, publishable, mode, webhook_secret = self._get_stripe_keys()
            if not secret:
                logger.error('Stripe secret key not configured')
                return False

            stripe.api_key = secret
            self._publishable_key = publishable
            self._webhook_secret = webhook_secret
            self._mode = mode
            self._initialized = True
            logger.info(f'Stripe processor initialized in {mode} mode')
            return True
        except Exception as e:
            logger.error(f'Failed to initialize Stripe: {e}')
            return False

    def _get_stripe_keys(self):
        """Get Stripe keys from config or environment."""
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

    def create_payment(
        self,
        amount_cents: int,
        currency: str,
        donor_email: str,
        donor_name: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent."""
        if not self._initialized:
            self.initialize()

        logger.info(f'Creating Stripe payment: {amount_cents} {currency} for {donor_email}')

        try:
            params = {
                'amount': amount_cents,
                'currency': currency.lower(),
                'metadata': metadata or {},
                'automatic_payment_methods': {'enabled': True},
                'receipt_email': donor_email,
            }

            # Add description for donor's bank statement
            params['description'] = f'Donation from {donor_name}'

            intent = stripe.PaymentIntent.create(**params)

            logger.info(f'Stripe PaymentIntent created: {intent.id}')

            return {
                'success': True,
                'client_secret': intent.client_secret,
                'payment_id': intent.id,
                'processor': self.code,
            }
        except stripe.error.StripeError as e:
            error_msg = e.user_message if hasattr(e, 'user_message') else str(e)
            logger.error(f'Stripe error: {error_msg}')
            return {
                'success': False,
                'error': error_msg,
                'processor': self.code,
            }

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for Stripe Elements on frontend."""
        if not self._initialized:
            self.initialize()

        return {
            'type': 'stripe_elements',
            'publishable_key': self._publishable_key,
            'locale': 'en',  # Always English for payment forms
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """Process Stripe webhook."""
        if not self._initialized:
            self.initialize()

        sig_header = headers.get('Stripe-Signature')
        if not sig_header:
            return {'success': False, 'error': 'Missing Stripe signature'}

        try:
            event = stripe.Webhook.construct_event(
                request_data, sig_header, self._webhook_secret
            )

            # Map Stripe events to normalized types
            event_map = {
                'payment_intent.succeeded': 'payment_succeeded',
                'payment_intent.payment_failed': 'payment_failed',
                'charge.refunded': 'refund_completed',
            }

            event_type = event_map.get(event['type'], event['type'])
            obj = event['data']['object']

            result = {
                'success': True,
                'event_type': event_type,
                'transaction_id': obj.get('id'),
                'amount_cents': obj.get('amount'),
                'currency': obj.get('currency', '').upper(),
                'raw_data': event,
                'processor': self.code,
            }

            # Extract donor info if available
            if 'receipt_email' in obj:
                result['donor_email'] = obj['receipt_email']
            if 'billing_details' in obj:
                billing = obj['billing_details']
                result['donor_name'] = billing.get('name')
                result['donor_email'] = result.get('donor_email') or billing.get('email')

            return result

        except stripe.error.SignatureVerificationError as e:
            logger.error(f'Stripe webhook signature verification failed: {e}')
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f'Stripe webhook processing error: {e}')
            return {'success': False, 'error': str(e)}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process a Stripe refund."""
        if not self._initialized:
            self.initialize()

        try:
            params = {'payment_intent': transaction_id}
            if amount_cents:
                params['amount'] = amount_cents

            refund = stripe.Refund.create(**params)

            return {
                'success': True,
                'refund_id': refund.id,
                'amount_refunded': refund.amount,
                'status': refund.status,
            }
        except stripe.error.StripeError as e:
            error_msg = e.user_message if hasattr(e, 'user_message') else str(e)
            logger.error(f'Stripe refund error: {error_msg}')
            return {
                'success': False,
                'error': error_msg,
            }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Retrieve a Stripe PaymentIntent."""
        if not self._initialized:
            self.initialize()

        try:
            intent = stripe.PaymentIntent.retrieve(transaction_id)
            return {
                'success': True,
                'transaction_id': intent.id,
                'amount_cents': intent.amount,
                'currency': intent.currency.upper(),
                'status': intent.status,
                'created': intent.created,
                'raw_data': intent,
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
            }

    def supports_currency(self, currency: str) -> bool:
        """Check if currency is supported."""
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """
        Estimate Stripe fee.

        Standard rate: 2.9% + $0.30 (USD)
        """
        # 2.9% + 30 cents
        percentage_fee = int(amount_cents * 0.029)
        fixed_fee = 30  # cents
        return percentage_fee + fixed_fee

    def is_test_mode(self) -> bool:
        """Check if in test mode."""
        if not self._initialized:
            self.initialize()
        return self._mode == 'test'

    def get_balance_transaction(self, bt_id: str) -> Dict[str, Any]:
        """Retrieve balance transaction for actual fee data."""
        if not self._initialized:
            self.initialize()

        try:
            bt = stripe.BalanceTransaction.retrieve(bt_id)
            return {
                'fee': bt.fee,
                'fee_details': [
                    {'type': fd.type, 'amount': fd.amount, 'description': fd.description}
                    for fd in bt.fee_details
                ],
                'net': bt.net,
            }
        except stripe.error.StripeError as e:
            logger.error(f'Error retrieving balance transaction: {e}')
            return {}
