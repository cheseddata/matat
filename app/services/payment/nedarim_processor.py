"""
Nedarim Plus payment processor implementation.

Handles payments via Nedarim Plus iframe for Israeli donors.
Supports ILS and USD currencies.

NOTE: This is a placeholder until credentials are obtained.
Full implementation requires MosadId and ApiPassword.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class NedarimProcessor(BasePaymentProcessor):
    """
    Nedarim Plus payment processor.

    Uses iframe-based payment flow for PCI compliance.
    Primary processor for Israeli donors and ILS currency.
    """

    IFRAME_URL = 'https://www.matara.pro/nedarimplus/iframe/'
    API_BASE_URL = 'https://matara.pro/nedarimplus/Reports/Manage3.aspx'
    WEBHOOK_IP = '18.194.219.73'  # Only accept webhooks from this IP

    SUPPORTED_CURRENCIES = ['ILS', 'USD']
    SUPPORTED_COUNTRIES = ['IL']  # Primary market

    # Currency codes used by Nedarim API
    CURRENCY_CODES = {
        'ILS': '1',
        'USD': '2',
    }

    @property
    def code(self) -> str:
        return 'nedarim'

    @property
    def name(self) -> str:
        return 'Nedarim Plus'

    @property
    def display_name(self) -> str:
        return 'Nedarim Plus'

    def initialize(self) -> bool:
        """Initialize with Nedarim Plus credentials."""
        self._mosad_id = self.config.get('mosad_id')
        self._api_password = self.config.get('api_password')

        if not self._mosad_id or not self._api_password:
            logger.warning('Nedarim Plus credentials not configured')
            self._initialized = False
            return False

        self._initialized = True
        logger.info(f'Nedarim Plus processor initialized for Mosad {self._mosad_id}')
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
        Prepare payment data for Nedarim iframe.

        Note: Actual payment happens client-side via PostMessage to iframe.
        This method prepares the data to be sent to the iframe.
        """
        if not self._initialized:
            if not self.initialize():
                return {'success': False, 'error': 'Nedarim Plus not configured'}

        # Convert cents to whole units (Nedarim expects shekels/dollars, not agorot/cents)
        amount = amount_cents / 100

        currency_code = self.CURRENCY_CODES.get(currency.upper(), '2')  # Default USD

        # Prepare PostMessage data for iframe
        iframe_data = {
            'Mosad': self._mosad_id,
            'ApiValid': self._api_password,
            'PaymentType': 'Ragil',  # One-time payment
            'Amount': str(amount),
            'Currency': currency_code,
            'Tashlumim': '1',  # Number of installments
            'ClientName': donor_name,
            'Mail': donor_email,
            'Groupe': 'Donations',
            'CallBack': metadata.get('callback_url', '') if metadata else '',
            'SuccessUrl': metadata.get('success_url', '') if metadata else '',
            'FailUrl': metadata.get('fail_url', '') if metadata else '',
        }

        # Add custom params for webhook mapping
        if metadata:
            if 'donor_id' in metadata:
                iframe_data['Param1'] = str(metadata['donor_id'])
            if 'salesperson_id' in metadata:
                iframe_data['Param2'] = str(metadata['salesperson_id'])
            if 'link_id' in metadata:
                iframe_data['Comments'] = f'link_id:{metadata["link_id"]}'

        return {
            'success': True,
            'iframe_data': iframe_data,
            'processor': self.code,
        }

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for Nedarim iframe on frontend."""
        return {
            'type': 'nedarim_iframe',
            'iframe_url': self.IFRAME_URL,
            'mosad_id': self._mosad_id if self._initialized else None,
            'api_valid': self._api_password if self._initialized else None,
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process Nedarim Plus webhook.

        IMPORTANT: Verify source IP is 18.194.219.73
        """
        import json

        # Verify source IP
        remote_ip = headers.get('X-Forwarded-For', headers.get('X-Real-IP', ''))
        if remote_ip and self.WEBHOOK_IP not in remote_ip:
            logger.warning(f'Nedarim webhook from unauthorized IP: {remote_ip}')
            return {'success': False, 'error': 'Unauthorized IP'}

        try:
            data = json.loads(request_data)

            # Check if this is a transaction or standing order webhook
            is_keva = 'KevaId' in data and data.get('KevaId') != '0'

            # Parse amount - Nedarim may send in agorot or shekels, verify!
            amount_raw = data.get('Amount', '0')
            # Assuming shekels, convert to agorot (smallest unit)
            amount_cents = int(float(amount_raw) * 100)

            # Map currency code to ISO
            currency_code = data.get('Currency', '1')
            currency = 'ILS' if currency_code == '1' else 'USD'

            result = {
                'success': True,
                'event_type': 'payment_succeeded',
                'transaction_id': data.get('TransactionId') or data.get('Shovar'),
                'amount_cents': amount_cents,
                'currency': currency,
                'donor_email': data.get('Mail'),
                'donor_name': data.get('ClientName'),
                'donor_phone': data.get('Phone'),
                'confirmation': data.get('Confirmation'),
                'last4': data.get('LastNum'),
                'card_expiry': data.get('Tokef'),
                'processor': self.code,
                'raw_data': data,
            }

            # Extract custom params
            if data.get('Param1'):
                result['donor_id'] = data['Param1']
            if data.get('Param2'):
                result['salesperson_id'] = data['Param2']

            # Standing order info
            if is_keva:
                result['keva_id'] = data['KevaId']
                result['is_recurring'] = True

            return result

        except json.JSONDecodeError as e:
            logger.error(f'Invalid JSON in Nedarim webhook: {e}')
            return {'success': False, 'error': 'Invalid JSON'}
        except Exception as e:
            logger.error(f'Nedarim webhook processing error: {e}')
            return {'success': False, 'error': str(e)}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process a Nedarim Plus refund.

        Note: Nedarim only supports full refunds per Israeli tax guidelines.
        """
        if not self._initialized:
            return {'success': False, 'error': 'Nedarim Plus not configured'}

        try:
            # Convert to shekels if amount provided
            params = {
                'Action': 'RefundTransaction',
                'MosadId': self._mosad_id,
                'ApiPassword': self._api_password,
                'TransactionId': transaction_id,
            }

            if amount_cents:
                params['RefundAmount'] = str(amount_cents / 100)

            response = requests.post(self.API_BASE_URL, data=params, timeout=30)
            result = response.json() if response.headers.get('Content-Type', '').startswith('application/json') else {'response': response.text}

            # Check for success (actual response format TBD)
            if response.status_code == 200:
                return {
                    'success': True,
                    'refund_id': transaction_id,  # Nedarim may not return separate refund ID
                    'amount_refunded': amount_cents,
                    'raw_response': result,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Refund failed'),
                }

        except Exception as e:
            logger.error(f'Nedarim refund error: {e}')
            return {'success': False, 'error': str(e)}

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Retrieve transaction from Nedarim Plus."""
        if not self._initialized:
            return {'success': False, 'error': 'Nedarim Plus not configured'}

        # Note: GetHistoryJson is rate-limited to 20 requests/hour
        # Consider caching or batch retrieval
        try:
            params = {
                'Action': 'GetHistoryJson',
                'MosadId': self._mosad_id,
                'ApiPassword': self._api_password,
                'LastId': '0',  # Start from beginning
            }

            response = requests.get(self.API_BASE_URL, params=params, timeout=30)
            transactions = response.json()

            # Find the specific transaction
            for txn in transactions:
                if str(txn.get('Shovar')) == str(transaction_id):
                    return {
                        'success': True,
                        'transaction_id': txn['Shovar'],
                        'amount_cents': int(float(txn.get('Amount', 0)) * 100),
                        'status': 'succeeded',
                        'raw_data': txn,
                    }

            return {'success': False, 'error': 'Transaction not found'}

        except Exception as e:
            logger.error(f'Error retrieving Nedarim transaction: {e}')
            return {'success': False, 'error': str(e)}

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def supports_country(self, country_code: str) -> bool:
        # Nedarim works best for Israel but accepts international cards
        return True

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """
        Estimate Nedarim fee.

        Typical rate varies by organization agreement.
        Using estimate of ~2% + fixed fee.
        """
        percentage_fee = int(amount_cents * 0.02)
        fixed_fee = 50 if currency.upper() == 'ILS' else 30  # Agorot or cents
        return percentage_fee + fixed_fee

    def sync_transactions(self, last_id: int = 0) -> Dict[str, Any]:
        """
        Sync recent transactions from Nedarim Plus.

        This is a safety net since Nedarim doesn't retry failed webhooks.
        Call periodically via cron/celery.

        Args:
            last_id: Last transaction ID received (for pagination)

        Returns:
            Dict with list of transactions and new last_id
        """
        if not self._initialized:
            return {'success': False, 'error': 'Nedarim Plus not configured'}

        try:
            params = {
                'Action': 'GetHistoryJson',
                'MosadId': self._mosad_id,
                'ApiPassword': self._api_password,
                'LastId': str(last_id),
            }

            response = requests.get(self.API_BASE_URL, params=params, timeout=30)
            transactions = response.json()

            return {
                'success': True,
                'transactions': transactions,
                'count': len(transactions),
            }

        except Exception as e:
            logger.error(f'Nedarim sync error: {e}')
            return {'success': False, 'error': str(e)}

    def get_standing_orders(self) -> Dict[str, Any]:
        """Get all standing orders (recurring payments)."""
        if not self._initialized:
            return {'success': False, 'error': 'Nedarim Plus not configured'}

        try:
            params = {
                'Action': 'GetKevaJson',
                'MosadId': self._mosad_id,
                'ApiPassword': self._api_password,
            }

            response = requests.get(self.API_BASE_URL, params=params, timeout=30)
            orders = response.json()

            return {
                'success': True,
                'orders': orders,
                'count': len(orders),
            }

        except Exception as e:
            logger.error(f'Error retrieving standing orders: {e}')
            return {'success': False, 'error': str(e)}
