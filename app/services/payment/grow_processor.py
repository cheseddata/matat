"""
Grow (Meshulam) payment processor implementation.

Most popular Israeli payment gateway.
Supports credit cards, Bit, Apple Pay, Google Pay.

CRITICAL: Uses form-data NOT JSON!
CRITICAL: Must call approveTransaction after webhook!

NOTE: Placeholder until credentials obtained.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class GrowProcessor(BasePaymentProcessor):
    """
    Grow (formerly Meshulam) payment processor.

    Key features:
    - Hosted payment page (expires in 10 minutes!)
    - Supports Bit, Apple Pay, Google Pay
    - MUST call approveTransaction after webhook
    - Uses multipart/form-data, NOT JSON
    - Server-side only (client-side blocked)
    """

    SANDBOX_URL = 'https://sandbox.meshulam.co.il'
    PRODUCTION_URL = 'https://api.meshulam.co.il'

    SUPPORTED_CURRENCIES = ['ILS', 'USD']

    @property
    def code(self) -> str:
        return 'grow'

    @property
    def display_name(self) -> str:
        return 'Grow (Meshulam)'

    def initialize(self) -> bool:
        """Initialize with Grow credentials."""
        self._page_code = self.config.get('page_code')
        self._user_id = self.config.get('user_id')
        self._api_key = self.config.get('api_key')
        self._sandbox = self.config.get('sandbox', True)

        if not self._page_code or not self._user_id:
            logger.warning('Grow credentials not configured')
            self._initialized = False
            return False

        self._base_url = self.SANDBOX_URL if self._sandbox else self.PRODUCTION_URL
        self._initialized = True
        logger.info(f'Grow processor initialized (sandbox={self._sandbox})')
        return True

    def _make_request(self, endpoint: str, data: Dict) -> Dict:
        """
        Make authenticated API request.

        CRITICAL: Uses form-data, NOT JSON!
        """
        data['pageCode'] = self._page_code
        data['userId'] = self._user_id
        if self._api_key:
            data['apiKey'] = self._api_key

        # CRITICAL: form-data, not JSON
        response = requests.post(
            f'{self._base_url}/api/light/server/1.0/{endpoint}',
            data=data,  # form-data!
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
        Create Grow payment session.

        WARNING: URL expires in 10 minutes!
        """
        if not self._initialized:
            if not self.initialize():
                return {'success': False, 'error': 'Grow not configured'}

        amount = amount_cents / 100  # Grow uses whole units
        metadata = metadata or {}

        data = {
            'sum': str(amount),
            'description': 'Donation',
            'successUrl': metadata.get('success_url', ''),
            'cancelUrl': metadata.get('cancel_url', ''),
            'notifyUrl': metadata.get('webhook_url', ''),
            'pageField[fullName]': donor_name,
            'pageField[email]': donor_email,
            'pageField[phone]': metadata.get('phone', ''),
            'saveToken': '1' if metadata.get('save_token') else '0',
        }

        # Custom fields for tracking
        if metadata.get('donor_id'):
            data['cField1'] = str(metadata['donor_id'])
        if metadata.get('salesperson_id'):
            data['cField2'] = str(metadata['salesperson_id'])

        try:
            result = self._make_request('createPaymentProcess', data)

            if result.get('status') == 1:
                return {
                    'success': True,
                    'payment_url': result['data'].get('url'),
                    'process_id': result['data'].get('processId'),
                    'expires_in_minutes': 10,  # Important warning!
                    'processor': self.code,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('err', {}).get('message', 'Unknown error'),
                    'processor': self.code,
                }
        except Exception as e:
            logger.error(f'Grow create payment error: {e}')
            return {'success': False, 'error': str(e)}

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for Grow hosted page."""
        return {
            'type': 'grow_redirect',
            'redirect': True,  # Redirect, not iframe
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process Grow webhook.

        CRITICAL: Must call approveTransaction after this!
        """
        import json

        try:
            data = json.loads(request_data) if request_data else {}

            transaction_id = data.get('transactionId')
            if not transaction_id:
                return {'success': False, 'error': 'Missing transactionId'}

            # CRITICAL: Must approve the transaction!
            approve_result = self._approve_transaction(transaction_id)
            if not approve_result.get('success'):
                logger.error(f'Failed to approve Grow transaction {transaction_id}')
                # Continue anyway to record the payment

            return {
                'success': True,
                'event_type': 'payment_succeeded',
                'transaction_id': transaction_id,
                'transaction_code': data.get('transactionCode'),
                'amount_cents': int(float(data.get('paymentSum', 0)) * 100),
                'currency': 'ILS',  # Grow primarily uses ILS
                'donor_name': data.get('fullName'),
                'donor_email': data.get('payerEmail'),
                'donor_phone': data.get('payerPhone'),
                'last4': data.get('cardSuffix'),
                'payment_source': data.get('paymentSource'),  # credit_card, bit, etc.
                'token': data.get('token'),
                'custom_fields': {
                    'cField1': data.get('purchaseCustomField', {}).get('cField1'),
                    'cField2': data.get('purchaseCustomField', {}).get('cField2'),
                },
                'processor': self.code,
                'raw_data': data,
                'approved': approve_result.get('success', False),
            }
        except Exception as e:
            logger.error(f'Grow webhook error: {e}')
            return {'success': False, 'error': str(e)}

    def _approve_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Approve a transaction.

        MANDATORY after webhook for standard payments!
        """
        if not self._initialized:
            return {'success': False, 'error': 'Grow not configured'}

        data = {'transactionId': transaction_id}

        try:
            result = self._make_request('approveTransaction', data)
            return {
                'success': result.get('status') == 1,
                'raw_result': result,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process Grow refund."""
        if not self._initialized:
            return {'success': False, 'error': 'Grow not configured'}

        data = {'transactionId': transaction_id}
        if amount_cents:
            data['refundSum'] = str(amount_cents / 100)

        try:
            result = self._make_request('refundTransaction', data)

            if result.get('status') == 1:
                return {
                    'success': True,
                    'refund_id': transaction_id,
                    'amount_refunded': amount_cents,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('err', {}).get('message', 'Refund failed'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction info."""
        if not self._initialized:
            return {'success': False, 'error': 'Grow not configured'}

        data = {'transactionId': transaction_id}
        try:
            result = self._make_request('getTransactionInfo', data)
            if result.get('status') == 1:
                return {
                    'success': True,
                    'transaction_id': transaction_id,
                    'raw_data': result.get('data'),
                }
            else:
                return {'success': False, 'error': 'Transaction not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def charge_token(
        self,
        token: str,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Charge a saved Grow token."""
        if not self._initialized:
            return {'success': False, 'error': 'Grow not configured'}

        metadata = metadata or {}

        data = {
            'sum': str(amount_cents / 100),
            'token': token,
            'paymentNum': '1',
        }

        # For recurring
        if metadata.get('recurring_debit_id'):
            data['recurringDebitId'] = metadata['recurring_debit_id']
        elif metadata.get('is_recurring'):
            data['isRecurringDebitPayment'] = '1'

        try:
            result = self._make_request('createTransactionWithToken', data)

            if result.get('status') == 1:
                return {
                    'success': True,
                    'transaction_id': result['data'].get('transactionId'),
                    'recurring_debit_id': result['data'].get('recurringDebitId'),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('err', {}).get('message', 'Token charge failed'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """Estimate Grow fee (~2.5% typical)."""
        return int(amount_cents * 0.025)
