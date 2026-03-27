"""
EasyCard payment processor implementation.

PCI DSS Level 1 certified Israeli gateway.
Supports redirect or iframe integration.

NOTE: Placeholder until credentials obtained.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class EasyCardProcessor(BasePaymentProcessor):
    """
    EasyCard payment processor.

    Key features:
    - PCI DSS Level 1 certified
    - Redirect or iframe (iframe needs SSL + allow="payment")
    - J4 = one-time, J5 = token billing
    - Supports Bit, Google Pay
    """

    API_BASE_URL = 'https://merchant.e-c.co.il/api'
    API_DOCS_URL = 'https://merchant.e-c.co.il/api-docs/index.html'

    SUPPORTED_CURRENCIES = ['ILS', 'USD']

    @property
    def code(self) -> str:
        return 'easycard'

    @property
    def display_name(self) -> str:
        return 'EasyCard'

    def initialize(self) -> bool:
        """Initialize with EasyCard credentials."""
        self._terminal_number = self.config.get('terminal_number')
        self._api_key = self.config.get('api_key')

        if not self._terminal_number or not self._api_key:
            logger.warning('EasyCard credentials not configured')
            self._initialized = False
            return False

        self._initialized = True
        logger.info(f'EasyCard processor initialized for terminal {self._terminal_number}')
        return True

    def _make_request(self, endpoint: str, data: Dict, method: str = 'POST') -> Dict:
        """Make authenticated API request."""
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
        }

        if method == 'POST':
            response = requests.post(
                f'{self.API_BASE_URL}/{endpoint}',
                json=data,
                headers=headers,
                timeout=30
            )
        else:
            response = requests.get(
                f'{self.API_BASE_URL}/{endpoint}',
                params=data,
                headers=headers,
                timeout=30
            )
        return response.json()

    def create_payment(
        self,
        amount_cents: int,
        currency: str,
        donor_email: str,
        donor_name: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create EasyCard payment session.

        Returns URL for redirect or iframe embedding.
        """
        if not self._initialized:
            if not self.initialize():
                return {'success': False, 'error': 'EasyCard not configured'}

        metadata = metadata or {}
        amount = amount_cents / 100

        # Deal type: J4 = one-time, J5 = token
        deal_type = 'J5' if metadata.get('save_token') else 'J4'

        data = {
            'terminal': self._terminal_number,
            'amount': amount,
            'currency': currency.upper(),
            'dealType': deal_type,
            'successUrl': metadata.get('success_url', ''),
            'failUrl': metadata.get('fail_url', ''),
            'callbackUrl': metadata.get('webhook_url', ''),
            'customerName': donor_name,
            'customerEmail': donor_email,
            'description': 'Donation',
        }

        try:
            result = self._make_request('payment/create', data)

            if result.get('success'):
                return {
                    'success': True,
                    'payment_url': result.get('paymentUrl'),
                    'payment_id': result.get('paymentId'),
                    'processor': self.code,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message', 'Unknown error'),
                    'processor': self.code,
                }
        except Exception as e:
            logger.error(f'EasyCard create payment error: {e}')
            return {'success': False, 'error': str(e)}

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for EasyCard redirect/iframe."""
        return {
            'type': 'easycard_redirect',
            'redirect': True,
            'iframe_allowed': True,
            'iframe_requires_ssl': True,
            'iframe_attribute': 'allow="payment"',
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """Process EasyCard webhook."""
        import json

        try:
            data = json.loads(request_data) if request_data else {}

            status = data.get('status')
            if status != 'success':
                return {
                    'success': False,
                    'event_type': 'payment_failed',
                    'error': data.get('message', 'Payment failed'),
                }

            return {
                'success': True,
                'event_type': 'payment_succeeded',
                'transaction_id': data.get('transactionId'),
                'confirmation': data.get('authNumber'),
                'amount_cents': int(float(data.get('amount', 0)) * 100),
                'currency': data.get('currency', 'ILS'),
                'token': data.get('token'),
                'last4': data.get('lastDigits'),
                'card_brand': data.get('cardBrand'),
                'payment_method': data.get('paymentMethod'),  # card, bit, google_pay
                'processor': self.code,
                'raw_data': data,
            }
        except Exception as e:
            logger.error(f'EasyCard webhook error: {e}')
            return {'success': False, 'error': str(e)}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process EasyCard refund."""
        if not self._initialized:
            return {'success': False, 'error': 'EasyCard not configured'}

        data = {
            'transactionId': transaction_id,
        }

        if amount_cents:
            data['amount'] = amount_cents / 100

        try:
            result = self._make_request('payment/refund', data)

            if result.get('success'):
                return {
                    'success': True,
                    'refund_id': result.get('refundId'),
                    'amount_refunded': amount_cents,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction details."""
        if not self._initialized:
            return {'success': False, 'error': 'EasyCard not configured'}

        try:
            result = self._make_request(
                f'payment/{transaction_id}',
                {},
                method='GET'
            )
            return {
                'success': True,
                'transaction_id': transaction_id,
                'raw_data': result,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def charge_token(
        self,
        token: str,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Charge a saved EasyCard token (J5)."""
        if not self._initialized:
            return {'success': False, 'error': 'EasyCard not configured'}

        data = {
            'terminal': self._terminal_number,
            'token': token,
            'amount': amount_cents / 100,
            'currency': currency.upper(),
            'dealType': 'J5',
        }

        try:
            result = self._make_request('payment/charge-token', data)

            if result.get('success'):
                return {
                    'success': True,
                    'transaction_id': result.get('transactionId'),
                    'confirmation': result.get('authNumber'),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """Estimate EasyCard fee (~2.5% typical)."""
        return int(amount_cents * 0.025)
