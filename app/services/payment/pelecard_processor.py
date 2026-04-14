"""
Pelecard payment processor.
API: https://gateway20.pelecard.biz/api/
Docs: https://pelecard.com/support/api/

Pelecard is one of Israel's largest CC processors (35+ years).
Supports: tokenization, recurring, installments, refunds.
Currencies: ILS, USD, EUR, GBP.
"""
import logging
import requests
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class PelecardProcessor(BasePaymentProcessor):
    """
    Pelecard Israeli credit card processor.

    Server-to-server REST JSON API.

    Config keys:
        terminal_number: Pelecard terminal ID
        username: API username
        password: API password
        sandbox: bool - True for test terminal (same URL, different credentials)
    """

    BASE_URL = 'https://gateway20.pelecard.biz/api'

    CURRENCY_MAP = {
        'ILS': '1',
        'USD': '2',
        'EUR': '978',
        'GBP': '826',
    }

    DEBIT_TYPE_MAP = {
        'regular': '51',
        'installments': '8',
        'credit': '6',
        'refund': '6',
        'standing_order': '9',
    }

    ERROR_CODES = {
        '000': 'Approved',
        '001': 'Card blocked',
        '002': 'Stolen card',
        '003': 'Contact card company',
        '004': 'Declined',
        '006': 'CVV error',
        '033': 'Card expired',
    }

    def __init__(self, config=None):
        super().__init__(config)

    @property
    def code(self) -> str:
        return 'pelecard'

    @property
    def name(self) -> str:
        return 'Pelecard'

    @property
    def display_name_he(self) -> str:
        return 'פלאקארד'

    @property
    def supported_currencies(self):
        return ['ILS', 'USD', 'EUR', 'GBP']

    @property
    def supported_countries(self):
        return ['IL']

    # ── Helpers ──────────────────────────────────────────────────────

    def _auth_params(self) -> Dict[str, str]:
        """Return authentication fields for every API request."""
        return {
            'TerminalNumber': self.config.get('terminal_number', ''),
            'User': self.config.get('username', ''),
            'Password': self.config.get('password', ''),
        }

    def _currency_code(self, currency: str) -> str:
        """Map currency string to Pelecard numeric code.

        ILS -> 1, USD -> 2, EUR -> 978, GBP -> 826.
        """
        code = self.CURRENCY_MAP.get(currency.upper())
        if not code:
            raise ValueError(f'Unsupported currency: {currency}')
        return code

    def _debit_type(self, type_str: str) -> str:
        """Map debit type string to Pelecard numeric code.

        regular -> 51, installments -> 8, credit/refund -> 6, standing_order -> 9.
        """
        return self.DEBIT_TYPE_MAP.get(type_str, '51')

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST JSON to a Pelecard API endpoint."""
        url = f'{self.BASE_URL}{endpoint}'
        try:
            resp = requests.post(url, json=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logger.error(f'Pelecard timeout: {endpoint}')
            return {'StatusCode': 'TIMEOUT', 'ErrorMessage': 'Request timed out'}
        except requests.exceptions.RequestException as e:
            logger.error(f'Pelecard network error: {endpoint} - {e}')
            return {'StatusCode': 'NETWORK', 'ErrorMessage': str(e)}
        except ValueError:
            logger.error(f'Pelecard invalid JSON: {endpoint}')
            return {'StatusCode': 'PARSE', 'ErrorMessage': 'Invalid JSON response'}

    def _is_success(self, response: Dict[str, Any]) -> bool:
        """StatusCode 000 = success."""
        return str(response.get('StatusCode', '')) == '000'

    def _error_message(self, response: Dict[str, Any]) -> str:
        """Build a human-readable error from the response."""
        status = str(response.get('StatusCode', 'UNKNOWN'))
        msg = response.get('ErrorMessage', '')
        known = self.ERROR_CODES.get(status, '')
        detail = msg or known or 'Unknown error'
        return f'{detail} (code: {status})'

    # ── Core Interface ───────────────────────────────────────────────

    def create_payment(
        self,
        amount: int,
        currency: str,
        card_data: Dict[str, str],
        donor_data: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a payment / charge a card via /PaymentGW/init.

        Args:
            amount: Amount in smallest currency unit (agorot/cents).
            currency: Currency code (ILS, USD, EUR, GBP).
            card_data: Dict with keys:
                - card_number, expiry_mmyy, cvv  (direct charge)
                - OR token  (recurring/token charge)
            donor_data: Optional dict with name, email, id_number, phone.
            **kwargs:
                debit_type: 'regular' | 'installments' | 'standing_order' (default: 'regular')
                num_payments: Number of installments (for debit_type='installments')
                first_payment: First installment amount
                other_payments: Subsequent installment amount
                shop_number: Shop/store number (default: '1000')

        Returns:
            Dict with success, transaction_id, confirmation, token, error, raw_response.
        """
        donor_data = donor_data or {}
        debit_type = kwargs.get('debit_type', 'regular')

        payload = {
            **self._auth_params(),
            'ShopNumber': kwargs.get('shop_number', '1000'),
            'DebitTotal': str(int(amount)),
            'DebitCurrency': self._currency_code(currency),
            'DebitType': self._debit_type(debit_type),
        }

        # Card details or saved token
        if card_data.get('token'):
            payload['Token'] = card_data['token']
        else:
            payload['CreditCardNumber'] = card_data.get('card_number', '').replace('-', '').replace(' ', '')
            payload['CreditCardDateMmYy'] = card_data.get('expiry_mmyy', '')
            payload['CVV2'] = card_data.get('cvv', '')

        # Installment fields
        if debit_type == 'installments':
            payload['NumberOfPayments'] = str(kwargs.get('num_payments', ''))
            payload['FirstPaymentTotal'] = str(kwargs.get('first_payment', ''))
            payload['OtherPaymentsTotal'] = str(kwargs.get('other_payments', ''))
        else:
            payload['NumberOfPayments'] = ''
            payload['FirstPaymentTotal'] = ''
            payload['OtherPaymentsTotal'] = ''

        # Donor ID number (Israeli TZ) in ParamX
        if donor_data.get('id_number'):
            payload['ParamX'] = donor_data['id_number']

        logger.info(f'Pelecard create_payment: {amount} {currency} type={debit_type}')
        data = self._post('/PaymentGW/init', payload)

        if self._is_success(data):
            card_masked = data.get('CreditCardNumber', '')
            result = {
                'success': True,
                'transaction_id': data.get('PelecardTransactionId', ''),
                'confirmation': data.get('ConfirmationKey', ''),
                'approval_no': data.get('ApprovalNo', ''),
                'token': data.get('Token', ''),
                'card_brand': data.get('CreditCardCompanyName', ''),
                'card_last4': card_masked[-4:] if card_masked else None,
                'processor': self.code,
                'raw_response': data,
            }
            logger.info(f'Pelecard payment OK: txn={result["transaction_id"]}')
            return result
        else:
            error = self._error_message(data)
            logger.warning(f'Pelecard payment failed: {error}')
            return {
                'success': False,
                'error': error,
                'processor': self.code,
                'raw_response': data,
            }

    def refund(
        self,
        transaction_id: str,
        amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Refund a transaction via /PaymentGW/refund.

        Args:
            transaction_id: Original PelecardTransactionId.
            amount: Refund amount in smallest unit. None for full refund.

        Returns:
            Dict with success, transaction_id, error, raw_response.
        """
        payload = {
            **self._auth_params(),
            'TransactionId': transaction_id,
        }
        if amount is not None:
            payload['RefundTotal'] = str(int(amount))

        logger.info(f'Pelecard refund: txn={transaction_id} amount={amount}')
        data = self._post('/PaymentGW/refund', payload)

        if self._is_success(data):
            logger.info(f'Pelecard refund OK: txn={transaction_id}')
            return {
                'success': True,
                'transaction_id': data.get('PelecardTransactionId', transaction_id),
                'confirmation': data.get('ConfirmationKey', ''),
                'processor': self.code,
                'raw_response': data,
            }
        else:
            error = self._error_message(data)
            logger.warning(f'Pelecard refund failed: {error}')
            return {
                'success': False,
                'error': error,
                'processor': self.code,
                'raw_response': data,
            }

    def charge_token(
        self,
        token: str,
        amount: int,
        currency: str,
        donor_data: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Charge a saved token (recurring payments).

        Delegates to create_payment with token in card_data.

        Args:
            token: Pelecard token from a previous successful charge.
            amount: Amount in smallest currency unit.
            currency: Currency code.
            donor_data: Optional donor info.
            **kwargs: Passed through to create_payment.

        Returns:
            Same as create_payment.
        """
        card_data = {'token': token}
        return self.create_payment(amount, currency, card_data, donor_data, **kwargs)

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Verify / retrieve transaction status via /PaymentGW/ValidateByUniqueKey.

        Args:
            transaction_id: Pelecard transaction ID or unique key.

        Returns:
            Dict with success, transaction details, or error.
        """
        payload = {
            **self._auth_params(),
            'UniqueKey': transaction_id,
        }

        logger.info(f'Pelecard get_transaction: {transaction_id}')
        data = self._post('/PaymentGW/ValidateByUniqueKey', payload)

        if self._is_success(data):
            return {
                'success': True,
                'transaction_id': data.get('PelecardTransactionId', ''),
                'confirmation': data.get('ConfirmationKey', ''),
                'approval_no': data.get('ApprovalNo', ''),
                'status_code': data.get('StatusCode'),
                'processor': self.code,
                'raw_response': data,
            }
        else:
            return {
                'success': False,
                'error': self._error_message(data),
                'processor': self.code,
                'raw_response': data,
            }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test API connectivity via /PaymentGW/GetTerminalData.

        Returns:
            Dict with success and message or terminal info.
        """
        payload = self._auth_params()

        logger.info('Pelecard test_connection')
        data = self._post('/PaymentGW/GetTerminalData', payload)

        if self._is_success(data):
            return {
                'success': True,
                'message': 'Connected to Pelecard',
                'terminal_data': data,
            }
        else:
            return {
                'success': False,
                'message': self._error_message(data),
            }

    def get_client_config(self) -> Dict[str, Any]:
        """Get frontend configuration for Pelecard."""
        return {
            'type': 'server_to_server',
            'processor': self.code,
            'name': self.name,
            'name_he': self.display_name_he,
            'supported_currencies': self.supported_currencies,
            'requires_card_entry': True,
            'supports_installments': True,
            'supports_token': True,
            'supports_refund': True,
            'max_installments': 36,
        }

    def supports_currency(self, currency: str) -> bool:
        """Check if currency is supported."""
        return currency.upper() in self.CURRENCY_MAP

    def estimate_fee(self, amount: int, currency: str) -> int:
        """
        Estimate Pelecard processing fee.

        Typical rate: ~1.5-2.5% for Israeli transactions.
        Using 2% as a conservative estimate.
        """
        return int(amount * 0.02)
