"""
PayMe payment processor implementation.

Modern Israeli payment gateway with hosted fields and hosted pages.
Supports credit cards, Bit, Apple Pay.

NOTE: Amounts in agorot!
NOTE: Placeholder until credentials obtained.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class PayMeProcessor(BasePaymentProcessor):
    """
    PayMe payment processor.

    Key features:
    - Hosted payment page OR hosted fields (JSAPI)
    - Supports Bit, Apple Pay
    - Amounts in agorot (smallest unit)
    - buyer_key for tokenization
    - Installments (ILS + Israeli cards only)
    """

    SANDBOX_URL = 'https://sandbox.payme.io/api'
    PRODUCTION_URL = 'https://api.payme.io'  # Verify with PayMe

    SUPPORTED_CURRENCIES = ['ILS', 'USD', 'EUR']

    @property
    def code(self) -> str:
        return 'payme'

    @property
    def display_name(self) -> str:
        return 'PayMe'

    def initialize(self) -> bool:
        """Initialize with PayMe credentials."""
        self._seller_id = self.config.get('seller_id')
        self._api_key = self.config.get('api_key')
        self._sandbox = self.config.get('sandbox', True)

        if not self._seller_id:
            logger.warning('PayMe credentials not configured')
            self._initialized = False
            return False

        self._base_url = self.SANDBOX_URL if self._sandbox else self.PRODUCTION_URL
        self._initialized = True
        logger.info(f'PayMe processor initialized (sandbox={self._sandbox})')
        return True

    def create_payment(
        self,
        amount_cents: int,
        currency: str,
        donor_email: str,
        donor_name: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create PayMe payment.

        NOTE: amount is in agorot/cents (smallest unit) - PayMe expects this!
        """
        if not self._initialized:
            if not self.initialize():
                return {'success': False, 'error': 'PayMe not configured'}

        metadata = metadata or {}

        data = {
            'seller_payme_id': self._seller_id,
            'sale_price': amount_cents,  # In agorot!
            'product_name': 'Donation',
            'currency': currency.upper(),
            'sale_callback_url': metadata.get('webhook_url', ''),
            'sale_return_url': metadata.get('success_url', ''),
            'installments': metadata.get('installments', 1),
            'language': metadata.get('language', 'en'),
            'buyer_name': donor_name,
            'buyer_email': donor_email,
            'buyer_phone': metadata.get('phone', ''),
            'capture_buyer': 1 if metadata.get('save_token') else 0,
        }

        try:
            response = requests.post(
                f'{self._base_url}/generate-sale',
                json=data,
                timeout=30
            )
            result = response.json()

            if result.get('status_code') == 0:
                return {
                    'success': True,
                    'payment_url': result.get('payme_sale_url'),
                    'sale_id': result.get('sale_payme_id'),
                    'processor': self.code,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('status_error_details', 'Unknown error'),
                    'processor': self.code,
                }
        except Exception as e:
            logger.error(f'PayMe create payment error: {e}')
            return {'success': False, 'error': str(e)}

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for PayMe hosted page or hosted fields."""
        return {
            'type': 'payme_hosted',
            'redirect': True,
            'seller_id': self._seller_id if self._initialized else None,
            'sandbox': self._sandbox if self._initialized else True,
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process PayMe webhook.

        PayMe includes signature for verification.
        """
        import json

        try:
            data = json.loads(request_data) if request_data else {}

            # TODO: Verify signature from headers

            sale_status = data.get('sale_status')
            if sale_status != 'completed':
                return {
                    'success': False,
                    'event_type': 'payment_failed',
                    'error': f'Sale status: {sale_status}',
                }

            return {
                'success': True,
                'event_type': 'payment_succeeded',
                'transaction_id': data.get('sale_payme_id'),
                'amount_cents': data.get('sale_price'),  # Already in agorot
                'currency': data.get('currency', 'ILS'),
                'buyer_key': data.get('buyer_key'),  # Token for recurring
                'buyer_email': data.get('buyer_email'),
                'buyer_name': data.get('buyer_name'),
                'processor': self.code,
                'raw_data': data,
            }
        except Exception as e:
            logger.error(f'PayMe webhook error: {e}')
            return {'success': False, 'error': str(e)}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process PayMe refund."""
        if not self._initialized:
            return {'success': False, 'error': 'PayMe not configured'}

        data = {
            'seller_payme_id': self._seller_id,
            'sale_payme_id': transaction_id,
        }

        if amount_cents:
            data['refund_amount'] = amount_cents

        try:
            response = requests.put(
                f'{self._base_url}/refund',
                json=data,
                timeout=30
            )
            result = response.json()

            if result.get('status_code') == 0:
                return {
                    'success': True,
                    'refund_id': result.get('refund_payme_id'),
                    'amount_refunded': amount_cents,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('status_error_details'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction details."""
        if not self._initialized:
            return {'success': False, 'error': 'PayMe not configured'}

        # PayMe transaction lookup API
        return {'success': True, 'transaction_id': transaction_id}

    def charge_token(
        self,
        token: str,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Charge a saved PayMe buyer_key."""
        if not self._initialized:
            return {'success': False, 'error': 'PayMe not configured'}

        metadata = metadata or {}

        data = {
            'seller_payme_id': self._seller_id,
            'sale_price': amount_cents,
            'product_name': 'Recurring Donation',
            'currency': currency.upper(),
            'buyer_key': token,
            'sale_callback_url': metadata.get('webhook_url', ''),
        }

        try:
            response = requests.post(
                f'{self._base_url}/generate-sale',
                json=data,
                timeout=30
            )
            result = response.json()

            if result.get('status_code') == 0:
                return {
                    'success': True,
                    'transaction_id': result.get('sale_payme_id'),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('status_error_details'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """Estimate PayMe fee (~2.5% typical)."""
        return int(amount_cents * 0.025)
