"""
Pelecard payment processor.
API: https://gateway20.pelecard.biz/api/
Docs: https://pelecard.com/support/api/

Pelecard is one of Israel's largest CC processors (35+ years).
Supports: tokenization, recurring, installments, refunds.
"""
import requests
import json
import logging
from .base import BasePaymentProcessor

log = logging.getLogger(__name__)

PELECARD_API_URL = 'https://gateway20.pelecard.biz/api'


class PelecardProcessor(BasePaymentProcessor):
    """Pelecard Israeli credit card processor."""

    def __init__(self, config=None):
        super().__init__(config)
        self.terminal = config.get('terminal', '') if config else ''
        self.user = config.get('user', '') if config else ''
        self.password = config.get('password', '') if config else ''
        self.is_test = config.get('test_mode', True) if config else True

    @property
    def code(self):
        return 'pelecard'

    @property
    def name(self):
        return 'Pelecard'

    @property
    def display_name_he(self):
        return 'פלאקארד'

    @property
    def supported_currencies(self):
        return ['ILS', 'USD', 'EUR', 'GBP']

    @property
    def supported_countries(self):
        return ['IL']

    def create_payment(self, amount, currency, card_data, donor_data=None, **kwargs):
        """Charge via Pelecard API.

        Pelecard uses a redirect-based flow for PCI compliance,
        but also supports server-to-server for tokenized charges.
        """
        amount_agorot = int(amount)
        installments = int(kwargs.get('installments', 1))

        # Currency codes: 1=ILS, 2=USD, 978=EUR
        currency_map = {'ILS': '1', 'USD': '2', 'EUR': '978', 'GBP': '826'}
        currency_code = currency_map.get(currency.upper(), '1')

        payload = {
            'TerminalNumber': self.terminal,
            'User': self.user,
            'Password': self.password,
            'ShopNumber': '1000',
            'CreditCardNumber': card_data.get('card_number', '').replace('-', '').replace(' ', ''),
            'CreditCardDateMmYy': card_data.get('expiry', ''),  # MMYY
            'CVV2': card_data.get('cvv', ''),
            'DebitTotal': str(amount_agorot),
            'DebitCurrency': currency_code,
            'DebitType': '51' if installments == 1 else '8',  # 51=regular, 8=installments
            'NumberOfPayments': str(installments) if installments > 1 else '',
            'FirstPaymentTotal': '',
            'OtherPaymentsTotal': '',
            'ParamX': donor_data.get('tz', '') if donor_data else '',
        }

        try:
            response = requests.post(
                f'{PELECARD_API_URL}/PaymentGW/init',
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            log.info(f"Pelecard response: {json.dumps(data)[:300]}")

            status_code = data.get('StatusCode', '-1')
            success = str(status_code) == '000'

            return {
                'success': success,
                'transaction_id': data.get('PelecardTransactionId', ''),
                'confirmation': data.get('ConfirmationKey', ''),
                'authorization_code': data.get('ApprovalNo', ''),
                'card_name': data.get('CreditCardCompanyName', ''),
                'token': data.get('Token', ''),  # For recurring!
                'ash_status': status_code,
                'ash_status_desc': data.get('ErrorMessage', ''),
                'error': None if success else f"Pelecard error {status_code}: {data.get('ErrorMessage', '')}",
                'raw_response': data,
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'raw_response': None}

    def charge_with_token(self, token, amount, currency='ILS', **kwargs):
        """Charge using a saved token (for recurring payments)."""
        amount_agorot = int(amount)
        currency_map = {'ILS': '1', 'USD': '2', 'EUR': '978'}

        payload = {
            'TerminalNumber': self.terminal,
            'User': self.user,
            'Password': self.password,
            'Token': token,
            'DebitTotal': str(amount_agorot),
            'DebitCurrency': currency_map.get(currency.upper(), '1'),
            'DebitType': '51',
        }

        try:
            response = requests.post(
                f'{PELECARD_API_URL}/PaymentGW/init',
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            success = str(data.get('StatusCode', '-1')) == '000'
            return {
                'success': success,
                'transaction_id': data.get('PelecardTransactionId', ''),
                'confirmation': data.get('ConfirmationKey', ''),
                'error': None if success else data.get('ErrorMessage', ''),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def refund(self, transaction_id, amount=None):
        """Refund a transaction."""
        payload = {
            'TerminalNumber': self.terminal,
            'User': self.user,
            'Password': self.password,
            'TransactionId': transaction_id,
        }
        if amount:
            payload['RefundTotal'] = str(int(amount))

        try:
            response = requests.post(
                f'{PELECARD_API_URL}/PaymentGW/refund',
                json=payload,
                timeout=30,
            )
            data = response.json()
            success = str(data.get('StatusCode', '-1')) == '000'
            return {'success': success, 'error': None if success else data.get('ErrorMessage', '')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_client_config(self):
        return {
            'processor': 'pelecard',
            'name': self.name,
            'name_he': self.display_name_he,
            'supported_currencies': self.supported_currencies,
            'requires_card_entry': True,
            'supports_installments': True,
            'supports_token': True,
            'supports_refund': True,
            'max_installments': 36,
        }

    def test_connection(self):
        try:
            payload = {
                'TerminalNumber': self.terminal,
                'User': self.user,
                'Password': self.password,
            }
            r = requests.post(f'{PELECARD_API_URL}/PaymentGW/GetTerminalData',
                              json=payload, timeout=10)
            if r.status_code == 200:
                return {'success': True, 'message': 'Connected to Pelecard'}
            return {'success': False, 'message': f'HTTP {r.status_code}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def estimate_fee(self, amount, currency):
        return int(amount * 0.015)  # ~1.5%
