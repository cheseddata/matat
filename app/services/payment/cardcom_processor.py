"""
CardCom payment processor implementation.

CardCom's killer feature: Auto-generates Israeli Section 46 donation receipts.
Uses LowProfile iframe for PCI compliance.

NOTE: Placeholder until credentials obtained.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class CardComProcessor(BasePaymentProcessor):
    """
    CardCom payment processor.

    Key features:
    - LowProfile iframe integration (PCI compliant)
    - Auto Section 46 donation receipts (DocType 400)
    - Webhook is GET (not POST!)
    - Token support for recurring
    """

    API_BASE_URL = 'https://secure.cardcom.solutions/api/v11/'

    # Document types for Israeli tax compliance
    DOC_TYPE_TAX_INVOICE = 300
    DOC_TYPE_TAX_INVOICE_RECEIPT = 305
    DOC_TYPE_CREDIT_NOTE = 310
    DOC_TYPE_RECEIPT = 320
    DOC_TYPE_DONATION_RECEIPT = 400  # Section 46!

    SUPPORTED_CURRENCIES = ['ILS', 'USD', 'EUR', 'GBP']

    # Currency codes (CoinID)
    CURRENCY_CODES = {
        'ILS': 1,
        'USD': 2,
        'EUR': 3,
        'GBP': 4,
    }

    @property
    def code(self) -> str:
        return 'cardcom'

    @property
    def display_name(self) -> str:
        return 'CardCom'

    def initialize(self) -> bool:
        """Initialize with CardCom credentials."""
        self._terminal_number = self.config.get('terminal_number')
        self._api_name = self.config.get('api_name')
        self._api_password = self.config.get('api_password')

        if not all([self._terminal_number, self._api_name, self._api_password]):
            logger.warning('CardCom credentials not configured')
            self._initialized = False
            return False

        # Terminal number MUST be integer
        try:
            self._terminal_number = int(self._terminal_number)
        except (ValueError, TypeError):
            logger.error('CardCom terminal_number must be an integer')
            self._initialized = False
            return False

        self._initialized = True
        logger.info(f'CardCom processor initialized for terminal {self._terminal_number}')
        return True

    def _make_request(self, endpoint: str, data: Dict) -> Dict:
        """Make authenticated API request."""
        data['TerminalNumber'] = self._terminal_number  # Must be integer!
        data['ApiName'] = self._api_name
        data['ApiPassword'] = self._api_password

        response = requests.post(
            f'{self.API_BASE_URL}{endpoint}',
            json=data,
            headers={'Content-Type': 'application/json'},
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
        Create CardCom LowProfile payment session.

        Returns URL to redirect/iframe.
        """
        if not self._initialized:
            if not self.initialize():
                return {'success': False, 'error': 'CardCom not configured'}

        amount = amount_cents / 100  # CardCom uses whole units
        coin_id = self.CURRENCY_CODES.get(currency.upper(), 2)

        metadata = metadata or {}

        data = {
            'Amount': amount,
            'Currency': coin_id,
            'SuccessRedirectUrl': metadata.get('success_url', ''),
            'FailedRedirectUrl': metadata.get('fail_url', ''),
            'WebHookUrl': metadata.get('webhook_url', ''),
            'ReturnValue': metadata.get('order_id', ''),
            'MaxNumOfPayments': 1,
            'Operation': 1,  # Charge + create token
            'Language': metadata.get('language', 'en'),
            'ProductName': 'Donation',
            'Document': {
                'DocTypeToCreate': self.DOC_TYPE_DONATION_RECEIPT,  # Section 46!
                'Name': donor_name,
                'Email': donor_email,
                'Products': [{
                    'Description': 'Donation',
                    'Price': amount,
                    'Quantity': 1
                }]
            }
        }

        try:
            result = self._make_request('LowProfile/Create', data)

            if result.get('OperationResponse') == 0:
                return {
                    'success': True,
                    'payment_url': result.get('Url'),
                    'low_profile_code': result.get('LowProfileCode'),
                    'processor': self.code,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('OperationResponseText', 'Unknown error'),
                    'processor': self.code,
                }
        except Exception as e:
            logger.error(f'CardCom create payment error: {e}')
            return {'success': False, 'error': str(e)}

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for CardCom LowProfile."""
        return {
            'type': 'cardcom_lowprofile',
            'iframe': True,
            'terminal_number': self._terminal_number if self._initialized else None,
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process CardCom webhook.

        IMPORTANT: CardCom webhooks are GET requests with query params!
        This method expects the query params as a dict in request_data.
        """
        import json

        try:
            # CardCom sends GET with query params, not POST body
            # The caller should pass query params as JSON
            params = json.loads(request_data) if request_data else {}

            low_profile_code = params.get('lowprofilecode')
            if not low_profile_code:
                return {'success': False, 'error': 'Missing lowprofilecode'}

            # Verify by calling GetLpResult
            result = self._get_payment_result(low_profile_code)
            if not result.get('success'):
                return result

            deal_response = result.get('DealResponse')
            if deal_response != 0:
                return {
                    'success': False,
                    'event_type': 'payment_failed',
                    'error': f'Deal failed with code {deal_response}',
                }

            return {
                'success': True,
                'event_type': 'payment_succeeded',
                'transaction_id': result.get('InternalDealNumber'),
                'amount_cents': int(float(result.get('Sum', 0)) * 100),
                'currency': 'ILS' if result.get('CoinId') == 1 else 'USD',
                'token': result.get('Token'),
                'confirmation': result.get('AuthNumber'),
                'last4': result.get('Last4CardDigits'),
                'invoice_number': result.get('InvoiceNumber'),
                'processor': self.code,
                'raw_data': result,
            }
        except Exception as e:
            logger.error(f'CardCom webhook error: {e}')
            return {'success': False, 'error': str(e)}

    def _get_payment_result(self, low_profile_code: str) -> Dict[str, Any]:
        """Get payment result from LowProfile code."""
        data = {'LowProfileCode': low_profile_code}
        try:
            result = self._make_request('LowProfile/GetLpResult', data)
            result['success'] = True
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process CardCom refund with auto credit note."""
        if not self._initialized:
            return {'success': False, 'error': 'CardCom not configured'}

        data = {
            'TransactionId': transaction_id,
            'CancelOnly': False,
            'Document': {
                'DocTypeToCreate': self.DOC_TYPE_CREDIT_NOTE  # Auto credit note
            }
        }

        if amount_cents:
            data['Amount'] = amount_cents / 100

        try:
            result = self._make_request('Transactions/RefundByTransactionId', data)

            if result.get('OperationResponse') == 0:
                return {
                    'success': True,
                    'refund_id': result.get('RefundTransactionId'),
                    'amount_refunded': amount_cents,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('OperationResponseText'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction details."""
        if not self._initialized:
            return {'success': False, 'error': 'CardCom not configured'}

        data = {'TransactionId': transaction_id}
        try:
            result = self._make_request('Transactions/GetById', data)
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
        """Charge a saved CardCom token."""
        if not self._initialized:
            return {'success': False, 'error': 'CardCom not configured'}

        metadata = metadata or {}
        coin_id = self.CURRENCY_CODES.get(currency.upper(), 2)

        data = {
            'Token': token,
            'SumToBill': amount_cents / 100,
            'CoinID': coin_id,
            'NumOfPayments': 1,
            'InvoiceHead': {
                'CustName': metadata.get('donor_name', 'Donor'),
                'SendByEmail': True,
                'Email': metadata.get('donor_email', ''),
                'Language': 'en',
                'CoinID': coin_id,
            },
            'InvoiceLines': [{
                'Description': 'Donation',
                'Price': amount_cents / 100,
                'Quantity': 1,
            }]
        }

        try:
            result = self._make_request('Transactions/ChargeWithToken', data)

            if result.get('ResponseCode') == 0:
                return {
                    'success': True,
                    'transaction_id': result.get('InternalDealNumber'),
                    'confirmation': result.get('AuthNumber'),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('Description', 'Token charge failed'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """Estimate CardCom fee (~2.5% typical)."""
        return int(amount_cents * 0.025)
