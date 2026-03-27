"""
Tranzila payment processor implementation.

Israel's oldest payment gateway with modern REST APIs.
Supports iframe integration with handshake verification.

NOTE: Placeholder until credentials obtained.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class TranzilaProcessor(BasePaymentProcessor):
    """
    Tranzila payment processor.

    Key features:
    - iframe with handshake verification
    - J5 mode for tokenization, J4 for one-time
    - 3D Secure support
    - Bit payment support
    """

    IFRAME_BASE_URL = 'https://direct.tranzila.com'
    API_BASE_URL = 'https://api.tranzila.com'
    LEGACY_API_URL = 'https://secure5.tranzila.com/cgi-bin/tranzila71u.cgi'

    # Currency codes
    CURRENCY_CODES = {
        'ILS': 1,
        'USD': 2,
        'GBP': 3,
        'EUR': 4,
        'JPY': 5,
    }

    SUPPORTED_CURRENCIES = ['ILS', 'USD', 'GBP', 'EUR']

    @property
    def code(self) -> str:
        return 'tranzila'

    @property
    def display_name(self) -> str:
        return 'Tranzila'

    def initialize(self) -> bool:
        """Initialize with Tranzila credentials."""
        self._terminal_name = self.config.get('terminal_name')
        self._terminal_password = self.config.get('terminal_password')
        self._app_key = self.config.get('app_key')

        if not self._terminal_name:
            logger.warning('Tranzila credentials not configured')
            self._initialized = False
            return False

        self._initialized = True
        logger.info(f'Tranzila processor initialized for terminal {self._terminal_name}')
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
        Create Tranzila payment session with iframe handshake.

        Flow:
        1. Request handshake token
        2. Return iframe URL with token
        3. After payment, verify via 3-sided handshake
        """
        if not self._initialized:
            if not self.initialize():
                return {'success': False, 'error': 'Tranzila not configured'}

        metadata = metadata or {}
        amount = amount_cents / 100
        currency_code = self.CURRENCY_CODES.get(currency.upper(), 2)

        # Build iframe URL with parameters
        iframe_url = f'{self.IFRAME_BASE_URL}/{self._terminal_name}/iframenew.php'

        iframe_params = {
            'aid': metadata.get('donor_id', ''),
            'action': 'single_payment',
            'amount': amount,
            'currency': currency_code,
            'ok_page': metadata.get('success_url', ''),
            'fail_page': metadata.get('fail_url', ''),
            'tokenize_on_single_payment': 'true' if metadata.get('save_token') else 'false',
        }

        return {
            'success': True,
            'iframe_url': iframe_url,
            'iframe_params': iframe_params,
            'processor': self.code,
        }

    def get_client_config(self) -> Dict[str, Any]:
        """Get config for Tranzila iframe."""
        return {
            'type': 'tranzila_iframe',
            'iframe': True,
            'terminal_name': self._terminal_name if self._initialized else None,
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process Tranzila handshake verification.

        Tranzila doesn't use traditional webhooks - uses redirect + handshake.
        """
        import json

        try:
            params = json.loads(request_data) if request_data else {}

            handshake_token = params.get('thtk')
            index = params.get('index')

            if not handshake_token:
                return {'success': False, 'error': 'Missing handshake token'}

            # Verify handshake server-to-server
            verify_result = self._verify_handshake(handshake_token, index)

            if verify_result.get('success'):
                return {
                    'success': True,
                    'event_type': 'payment_succeeded',
                    'transaction_id': verify_result.get('transaction_id'),
                    'token': verify_result.get('token'),
                    'last4': verify_result.get('last4'),
                    'processor': self.code,
                    'raw_data': verify_result,
                }
            else:
                return {
                    'success': False,
                    'event_type': 'payment_failed',
                    'error': verify_result.get('error'),
                }
        except Exception as e:
            logger.error(f'Tranzila webhook error: {e}')
            return {'success': False, 'error': str(e)}

    def _verify_handshake(self, token: str, index: str) -> Dict[str, Any]:
        """Verify 3-sided handshake."""
        # Implementation depends on exact Tranzila handshake API
        # Placeholder
        return {'success': True, 'transaction_id': token}

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process Tranzila refund."""
        if not self._initialized:
            return {'success': False, 'error': 'Tranzila not configured'}

        data = {
            'supplier': self._terminal_name,
            'TranzilaPW': self._terminal_password,
            'tranmode': 'C',  # Credit/refund
            'autession': transaction_id,
        }

        if amount_cents:
            data['sum'] = amount_cents / 100

        try:
            response = requests.post(self.LEGACY_API_URL, data=data, timeout=30)
            # Parse response (format depends on API version)
            return {'success': True, 'refund_id': transaction_id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction details."""
        if not self._initialized:
            return {'success': False, 'error': 'Tranzila not configured'}

        # Use report API
        return {'success': True, 'transaction_id': transaction_id}

    def charge_token(
        self,
        token: str,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Charge a saved Tranzila token."""
        if not self._initialized:
            return {'success': False, 'error': 'Tranzila not configured'}

        currency_code = self.CURRENCY_CODES.get(currency.upper(), 2)

        data = {
            'supplier': self._terminal_name,
            'TranzilaPW': self._terminal_password,
            'TranzilaTK': token,
            'sum': amount_cents / 100,
            'currency': currency_code,
        }

        try:
            response = requests.post(
                'https://secure5.tranzila.com/cgi-bin/tranzila31tk.cgi',
                data=data,
                timeout=30
            )
            # Parse response
            return {'success': True, 'transaction_id': token}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """Estimate Tranzila fee (~2.5% typical)."""
        return int(amount_cents * 0.025)
