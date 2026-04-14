"""
Yaad (iCard) payment processor implementation.

Simple REST API with form-encoded POST to https://icom.yaad.net/p/
Supports one-time charges, tokenization, recurring (token-based), refunds,
and installments (up to 36). Currencies: ILS, USD, EUR, GBP.

Docs: https://yaad.net/
"""
import logging
from typing import Dict, Any, Optional
from urllib.parse import parse_qs

import requests

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)

# Yaad CCode response meanings
CCODE_MESSAGES = {
    '0': 'Approved',
    '1': 'Card declined',
    '2': 'Card stolen',
    '3': 'Call card company',
    '4': 'General error',
    '6': 'CVV error',
    '10': 'Partial amount approved',
    '33': 'Card expired',
    '99': 'System error',
}

CURRENCY_MAP = {
    'ILS': 1,
    'USD': 2,
    'EUR': 3,
    'GBP': 4,
}


class YaadProcessor(BasePaymentProcessor):
    """
    Yaad (iCard) payment processor.

    Israeli payment gateway with simple REST API.
    Auth via Masof (terminal ID), PassP (password), and KEY (API key).
    """

    BASE_URL = 'https://icom.yaad.net/p/'
    SUPPORTED_CURRENCIES = ['ILS', 'USD', 'EUR', 'GBP']

    @property
    def code(self) -> str:
        return 'yaad'

    @property
    def name(self) -> str:
        return 'Yaad'

    @property
    def display_name_he(self) -> str:
        return 'יעד'

    @property
    def supported_currencies(self):
        return self.SUPPORTED_CURRENCIES

    @property
    def supported_countries(self):
        return ['IL']

    def _get_credentials(self) -> Dict[str, str]:
        """Return Masof, PassP, KEY from processor config."""
        return {
            'Masof': self.config.get('masof', ''),
            'PassP': self.config.get('passp', ''),
            'KEY': self.config.get('api_key', ''),
        }

    def _is_sandbox(self) -> bool:
        return self.config.get('sandbox', True)

    @staticmethod
    def _currency_code(currency: str) -> int:
        """Map currency string to Yaad numeric code. Defaults to 1 (ILS)."""
        return CURRENCY_MAP.get(currency.upper(), 1)

    def _post(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send form-encoded POST to Yaad API and parse the response.

        Yaad may return URL-encoded or JSON. We try JSON first,
        then fall back to URL-encoded query-string parsing.
        """
        try:
            resp = requests.post(
                self.BASE_URL,
                data=params,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f'Yaad HTTP error: {e}')
            return {'CCode': '-1', 'errMsg': str(e)}

        # Try JSON first
        try:
            return resp.json()
        except ValueError:
            pass

        # Fall back to URL-encoded
        text = resp.text.strip()
        if '=' in text:
            parsed = parse_qs(text, keep_blank_values=True)
            return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

        return {'CCode': '-1', 'errMsg': f'Unexpected response: {text}'}

    def _is_success(self, result: Dict[str, Any]) -> bool:
        return str(result.get('CCode', '')) == '0'

    def _error_message(self, result: Dict[str, Any]) -> str:
        ccode = str(result.get('CCode', ''))
        err = result.get('errMsg', '')
        default = CCODE_MESSAGES.get(ccode, f'Unknown error (CCode={ccode})')
        return err if err else default

    # ------------------------------------------------------------------ #
    # BasePaymentProcessor interface
    # ------------------------------------------------------------------ #

    def create_payment(
        self,
        amount: float,
        currency: str,
        card_data: Dict[str, Any],
        donor_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a one-time payment.

        Args:
            amount: Charge amount (e.g. 18.00).
            currency: 'ILS', 'USD', 'EUR', 'GBP'.
            card_data: Dict with keys: number, exp_month, exp_year, cvv.
            donor_data: Optional dict with: name, last_name, email, phone, user_id.
            **kwargs: installments (int), order (str), info (str).

        Returns:
            Dict with success, transaction_id, confirmation, token, raw_response, error.
        """
        donor = donor_data or {}
        params = {
            **self._get_credentials(),
            'action': 'pay',
            'CC': card_data.get('number', ''),
            'Tmonth': str(card_data.get('exp_month', '')).zfill(2),
            'Tyear': str(card_data.get('exp_year', '')),
            'CVV': card_data.get('cvv', ''),
            'Amount': f'{amount:.2f}',
            'Currency': self._currency_code(currency),
            'Coin': self._currency_code(currency),
            'Tash': kwargs.get('installments', 1),
            'UserId': donor.get('user_id', ''),
            'ClientName': donor.get('name', ''),
            'ClientLName': donor.get('last_name', ''),
            'phone': donor.get('phone', ''),
            'email': donor.get('email', ''),
            'Order': kwargs.get('order', ''),
            'Info': kwargs.get('info', ''),
            'J5': 'True',
            'MoreData': 'True',
            'Sign': 'True',
        }

        logger.info(f'Yaad create_payment: {amount} {currency}')
        result = self._post(params)

        if self._is_success(result):
            return {
                'success': True,
                'transaction_id': result.get('Id', ''),
                'confirmation': result.get('ACode', ''),
                'token': result.get('Token', ''),
                'last4': result.get('L4digit', ''),
                'brand': result.get('Brand', ''),
                'processor': self.code,
                'raw_response': result,
            }

        error = self._error_message(result)
        logger.warning(f'Yaad payment failed: {error}')
        return {
            'success': False,
            'error': error,
            'processor': self.code,
            'raw_response': result,
        }

    def get_client_config(self) -> Dict[str, Any]:
        """
        Yaad uses server-side card data (no iframe/hosted fields).
        Return minimal config for frontend.
        """
        return {
            'type': 'server_side',
            'processor': self.code,
            'supported_currencies': self.SUPPORTED_CURRENCIES,
            'max_installments': 36,
        }

    def refund(
        self,
        transaction_id: str,
        amount: Optional[float] = None,
        credit_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Refund a transaction.

        Args:
            transaction_id: Original Yaad transaction ID.
            amount: Refund amount (full refund if None).
            credit_id: Original approval/authorization code (ACode).
        """
        params = {
            **self._get_credentials(),
            'action': 'refund',
            'TransId': transaction_id,
        }
        if amount is not None:
            params['Amount'] = f'{amount:.2f}'
        if credit_id:
            params['CreditId'] = credit_id

        logger.info(f'Yaad refund: trans={transaction_id} amount={amount}')
        result = self._post(params)

        if self._is_success(result):
            return {
                'success': True,
                'transaction_id': result.get('Id', transaction_id),
                'processor': self.code,
                'raw_response': result,
            }

        error = self._error_message(result)
        logger.warning(f'Yaad refund failed: {error}')
        return {
            'success': False,
            'error': error,
            'processor': self.code,
            'raw_response': result,
        }

    def charge_token(
        self,
        token: str,
        amount: float,
        currency: str,
        donor_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Charge a saved token (recurring / repeat payment).

        Args:
            token: Token string from a previous payment.
            amount: Charge amount.
            currency: Currency code.
            donor_data: Optional dict with user_id, info, etc.
            **kwargs: installments (int), info (str).
        """
        donor = donor_data or {}
        params = {
            **self._get_credentials(),
            'action': 'soft',
            'Token': token,
            'Amount': f'{amount:.2f}',
            'Currency': self._currency_code(currency),
            'Tash': kwargs.get('installments', 1),
            'UserId': donor.get('user_id', ''),
            'Info': kwargs.get('info', ''),
        }

        logger.info(f'Yaad charge_token: {amount} {currency}')
        result = self._post(params)

        if self._is_success(result):
            return {
                'success': True,
                'transaction_id': result.get('Id', ''),
                'confirmation': result.get('ACode', ''),
                'processor': self.code,
                'raw_response': result,
            }

        error = self._error_message(result)
        logger.warning(f'Yaad charge_token failed: {error}')
        return {
            'success': False,
            'error': error,
            'processor': self.code,
            'raw_response': result,
        }

    def tokenize_card(self, card_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a card without charging (action=APISign).

        Args:
            card_data: Dict with number, exp_month, exp_year, cvv.

        Returns:
            Dict with success, token, error.
        """
        params = {
            **self._get_credentials(),
            'action': 'APISign',
            'CC': card_data.get('number', ''),
            'Tmonth': str(card_data.get('exp_month', '')).zfill(2),
            'Tyear': str(card_data.get('exp_year', '')),
            'CVV': card_data.get('cvv', ''),
            'Amount': '0',
            'Sign': 'True',
        }

        logger.info('Yaad tokenize_card')
        result = self._post(params)

        if self._is_success(result):
            return {
                'success': True,
                'token': result.get('Token', ''),
                'last4': result.get('L4digit', ''),
                'brand': result.get('Brand', ''),
                'expiry': result.get('Tokef', ''),
                'processor': self.code,
                'raw_response': result,
            }

        error = self._error_message(result)
        logger.warning(f'Yaad tokenize failed: {error}')
        return {
            'success': False,
            'error': error,
            'processor': self.code,
            'raw_response': result,
        }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Retrieve transaction details (action=getTransData)."""
        params = {
            **self._get_credentials(),
            'action': 'getTransData',
            'TransId': transaction_id,
        }

        logger.info(f'Yaad get_transaction: {transaction_id}')
        result = self._post(params)

        if self._is_success(result):
            return {
                'success': True,
                'transaction_id': transaction_id,
                'processor': self.code,
                'raw_response': result,
            }

        error = self._error_message(result)
        return {
            'success': False,
            'error': error,
            'processor': self.code,
            'raw_response': result,
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Verify credentials by calling getTransData with a dummy ID.
        A credentials error returns a distinct CCode vs. "not found".
        """
        params = {
            **self._get_credentials(),
            'action': 'getTransData',
            'TransId': '0',
        }

        try:
            result = self._post(params)
            ccode = str(result.get('CCode', ''))
            # CCode 0 or a "not found" style error means credentials are valid
            # CCode 4 / 99 with auth-related errMsg means bad credentials
            err = result.get('errMsg', '').lower()
            if 'password' in err or 'masof' in err or 'auth' in err:
                return {
                    'success': False,
                    'message': f'Authentication failed: {result.get("errMsg", "")}',
                }
            return {
                'success': True,
                'message': f'Connected to Yaad (CCode={ccode})',
            }
        except Exception as e:
            logger.error(f'Yaad test_connection error: {e}')
            return {
                'success': False,
                'message': str(e),
            }

    def estimate_fee(self, amount: float, currency: str) -> float:
        """
        Estimate Yaad processing fee.
        Typical rate: ~1.5-2.5% for Israeli nonprofits.
        Using 2% as a reasonable default estimate.
        """
        return round(amount * 0.02, 2)

    def supports_currency(self, currency: str) -> bool:
        return currency.upper() in self.SUPPORTED_CURRENCIES
