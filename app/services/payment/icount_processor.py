"""
iCount payment + invoicing processor implementation.

Dual purpose: payment processing AND invoice/receipt generation.
Israeli accounting software with built-in payment.

NOTE: Rate limit 30 requests/minute!
NOTE: Placeholder until credentials obtained.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class ICountProcessor(BasePaymentProcessor):
    """
    iCount payment processor.

    Key features:
    - Combined payment + invoicing
    - Bearer token authentication
    - Auto-generates Israeli tax documents
    - Rate limit: 30 requests/minute
    """

    API_BASE_URL = 'https://api-v3.icount.co.il'

    # Document types
    DOC_INVOICE = 'invoice'
    DOC_INVOICE_RECEIPT = 'invrec'
    DOC_RECEIPT = 'receipt'  # For donations
    DOC_REFUND = 'refund'

    SUPPORTED_CURRENCIES = ['ILS', 'USD', 'EUR', 'GBP']

    @property
    def code(self) -> str:
        return 'icount'

    @property
    def display_name(self) -> str:
        return 'iCount'

    def initialize(self) -> bool:
        """Initialize with iCount API token."""
        self._api_token = self.config.get('api_token')

        if not self._api_token:
            logger.warning('iCount API token not configured')
            self._initialized = False
            return False

        self._initialized = True
        logger.info('iCount processor initialized')
        return True

    def _make_request(self, endpoint: str, data: Dict) -> Dict:
        """Make authenticated API request with Bearer token."""
        headers = {
            'Authorization': f'Bearer {self._api_token}',
            'Content-Type': 'application/json',
        }

        response = requests.post(
            f'{self.API_BASE_URL}/{endpoint}',
            json=data,
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
        Create iCount payment with receipt.

        iCount can charge directly or via hosted page.
        """
        if not self._initialized:
            if not self.initialize():
                return {'success': False, 'error': 'iCount not configured'}

        metadata = metadata or {}
        amount = amount_cents / 100

        # Create document (receipt for donations)
        doc_data = {
            'doctype': self.DOC_RECEIPT,
            'client_name': donor_name,
            'email': donor_email,
            'currency_code': currency.upper(),
            'lang': metadata.get('language', 'en'),
            'items': [{
                'description': 'Donation',
                'quantity': 1,
                'unitprice': amount,
            }],
            'send_email': True,
        }

        if metadata.get('vat_id'):
            doc_data['vat_id'] = metadata['vat_id']

        try:
            result = self._make_request('doc/create', doc_data)

            if result.get('status'):
                return {
                    'success': True,
                    'document_id': result.get('doc_id'),
                    'document_number': result.get('doc_number'),
                    'document_url': result.get('doc_url'),
                    'processor': self.code,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error_description', 'Unknown error'),
                    'processor': self.code,
                }
        except Exception as e:
            logger.error(f'iCount create payment error: {e}')
            return {'success': False, 'error': str(e)}

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for iCount hosted page."""
        return {
            'type': 'icount_hosted',
            'redirect': True,
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """Process iCount webhook/callback."""
        import json

        try:
            data = json.loads(request_data) if request_data else {}

            return {
                'success': True,
                'event_type': 'payment_succeeded',
                'transaction_id': data.get('transaction_id'),
                'document_id': data.get('doc_id'),
                'document_number': data.get('doc_number'),
                'amount_cents': int(float(data.get('amount', 0)) * 100),
                'currency': data.get('currency', 'ILS'),
                'processor': self.code,
                'raw_data': data,
            }
        except Exception as e:
            logger.error(f'iCount webhook error: {e}')
            return {'success': False, 'error': str(e)}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process iCount refund with credit note."""
        if not self._initialized:
            return {'success': False, 'error': 'iCount not configured'}

        # Create refund document (credit note)
        doc_data = {
            'doctype': self.DOC_REFUND,
            'related_doc_id': transaction_id,
        }

        if amount_cents:
            doc_data['amount'] = amount_cents / 100

        try:
            result = self._make_request('doc/create', doc_data)

            if result.get('status'):
                return {
                    'success': True,
                    'refund_id': result.get('doc_id'),
                    'amount_refunded': amount_cents,
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error_description'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction/document details."""
        if not self._initialized:
            return {'success': False, 'error': 'iCount not configured'}

        # Document lookup API
        return {'success': True, 'transaction_id': transaction_id}

    def charge_token(
        self,
        token: str,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Charge a saved iCount token."""
        if not self._initialized:
            return {'success': False, 'error': 'iCount not configured'}

        data = {
            'token': token,
            'amount': amount_cents / 100,
            'currency': currency.upper(),
        }

        try:
            result = self._make_request('cc/charge', data)

            if result.get('status'):
                return {
                    'success': True,
                    'transaction_id': result.get('transaction_id'),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error_description'),
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def create_client(self, name: str, email: str, **kwargs) -> Dict[str, Any]:
        """Create iCount client for recurring/CRM."""
        if not self._initialized:
            return {'success': False, 'error': 'iCount not configured'}

        data = {
            'client_name': name,
            'email': email,
            **kwargs
        }

        try:
            result = self._make_request('client/create', data)
            return {
                'success': result.get('status', False),
                'client_id': result.get('client_id'),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """Estimate iCount fee (~2.5% typical)."""
        return int(amount_cents * 0.025)
