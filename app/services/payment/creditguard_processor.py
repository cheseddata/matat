"""
CreditGuard (Hyp) payment processor implementation.

Handles payments via CreditGuard XML API over HTTPS.
Supports ILS, USD, EUR, GBP currencies.
Uses XML request/response protocol with terminal authentication.

API Docs: https://www.creditguard.co.il/wp-content/uploads/2022/11/20221024-3_2_45-EMV-XML-API.pdf
"""
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from urllib.parse import urlencode

import requests

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)

# CreditGuard result codes
RESULT_CODES = {
    '000': 'Approved',
    '001': 'Card blocked',
    '002': 'Stolen card',
    '003': 'Contact company',
    '004': 'Declined',
    '006': 'CVV wrong',
    '012': 'Invalid transaction',
    '036': 'Card expired',
}

# Currency codes used by CreditGuard
CURRENCY_MAP = {
    'ILS': 'ILS',
    'USD': 'USD',
    'EUR': 'EUR',
    'GBP': 'GBP',
}


class CreditGuardProcessor(BasePaymentProcessor):
    """
    CreditGuard (Hyp) payment processor.

    Processes credit card transactions via XML API.
    Primary gateway for Israeli credit card processing.
    Supports charges, installments, refunds, and tokenization.
    """

    PRODUCTION_URL = 'https://meshulam.creditguard.co.il/xpo/Relay'
    TEST_URL = 'https://meshulam-test.creditguard.co.il/xpo/Relay'

    SUPPORTED_CURRENCIES = ['ILS', 'USD', 'EUR', 'GBP']
    SUPPORTED_COUNTRIES = ['IL']

    API_VERSION = '2000'

    @property
    def code(self) -> str:
        return 'creditguard'

    @property
    def name(self) -> str:
        return 'CreditGuard'

    @property
    def display_name_he(self) -> str:
        return 'קרדיטגארד'

    @property
    def supported_currencies(self):
        return self.SUPPORTED_CURRENCIES

    @property
    def supported_countries(self):
        return self.SUPPORTED_COUNTRIES

    def _get_relay_url(self) -> str:
        """Return production or test URL based on config."""
        if self.config.get('sandbox', True):
            return self.TEST_URL
        return self.PRODUCTION_URL

    def _get_terminal(self) -> str:
        return self.config.get('terminal_number', '')

    def _get_username(self) -> str:
        return self.config.get('username', '')

    def _get_password(self) -> str:
        return self.config.get('password', '')

    def _get_mid(self) -> str:
        return self.config.get('mid', '') or self._get_terminal()

    def _build_xml(self, command: str, deal_params: Dict[str, str]) -> str:
        """
        Build CreditGuard XML request.

        Args:
            command: API command (e.g., 'doDeal', 'inquireTransactions')
            deal_params: Dict of parameters for the command element

        Returns:
            XML string wrapped in <ashrait> tags
        """
        root = ET.Element('ashrait')
        request_el = ET.SubElement(root, 'request')

        ET.SubElement(request_el, 'version').text = self.API_VERSION
        ET.SubElement(request_el, 'language').text = 'EN'
        ET.SubElement(request_el, 'command').text = command

        command_el = ET.SubElement(request_el, command)
        ET.SubElement(command_el, 'terminalNumber').text = self._get_terminal()
        ET.SubElement(command_el, 'user').text = self._get_username()
        ET.SubElement(command_el, 'mid').text = self._get_mid()

        for key, value in deal_params.items():
            ET.SubElement(command_el, key).text = str(value) if value is not None else ''

        return ET.tostring(root, encoding='unicode', xml_declaration=False)

    def _post_xml(self, xml_body: str) -> str:
        """
        POST XML to CreditGuard relay endpoint.

        Args:
            xml_body: The XML string to send as int_in

        Returns:
            Response body as string

        Raises:
            requests.RequestException: On HTTP errors
        """
        url = self._get_relay_url()
        data = urlencode({
            'user': self._get_username(),
            'password': self._get_password(),
            'int_in': xml_body,
        })
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        logger.debug(f'CreditGuard POST to {url}')
        response = requests.post(url, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text

    def _parse_response(self, xml_text: str, command: str = 'doDeal') -> Dict[str, Any]:
        """
        Parse CreditGuard XML response.

        The response has a nested structure:
        ashrait > response > doDeal > cgGatewayResponseXml > ashrait > response

        Args:
            xml_text: Raw XML response string
            command: The command name to look for in response

        Returns:
            Dict with parsed fields: result, message, tranId, authNumber,
            cardToken, cardMask, cardBrand, etc.
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f'CreditGuard XML parse error: {e}')
            return {'result': '999', 'message': f'XML parse error: {e}'}

        # Navigate outer response
        outer_response = root.find('response')
        if outer_response is None:
            return {'result': '999', 'message': 'Missing outer response element'}

        command_el = outer_response.find(command)
        if command_el is None:
            # Some commands return directly in outer response
            result_el = outer_response.find('result')
            if result_el is not None:
                return {
                    'result': result_el.text or '999',
                    'message': self._get_text(outer_response, 'message', 'Unknown'),
                    'userMessage': self._get_text(outer_response, 'userMessage', ''),
                }
            return {'result': '999', 'message': f'Missing {command} element in response'}

        # Check for cgGatewayResponseXml (nested response)
        gateway_xml_el = command_el.find('cgGatewayResponseXml')
        if gateway_xml_el is not None:
            # Parse the inner XML
            inner_text = gateway_xml_el.text
            if inner_text:
                try:
                    inner_root = ET.fromstring(inner_text)
                    inner_response = inner_root.find('response')
                    if inner_response is not None:
                        return self._extract_response_fields(inner_response)
                except ET.ParseError:
                    pass

            # Sometimes cgGatewayResponseXml contains child elements directly
            inner_ashrait = gateway_xml_el.find('ashrait')
            if inner_ashrait is not None:
                inner_response = inner_ashrait.find('response')
                if inner_response is not None:
                    return self._extract_response_fields(inner_response)

        # Fall back to direct fields in command element
        return self._extract_response_fields(command_el)

    def _extract_response_fields(self, element: ET.Element) -> Dict[str, Any]:
        """Extract standard response fields from an XML element."""
        fields = [
            'result', 'message', 'userMessage', 'tranId', 'authNumber',
            'cardToken', 'cardMask', 'cardBrand', 'cardExpiration',
            'slaveTerminalNumber', 'slaveTerminalSequence', 'total',
            'firstPayment', 'periodicalPayment', 'numberOfPayments',
            'currency', 'transactionType', 'creditType',
        ]
        data = {}
        for field in fields:
            val = self._get_text(element, field)
            if val is not None:
                data[field] = val
        return data

    @staticmethod
    def _get_text(element: ET.Element, tag: str, default: str = None) -> Optional[str]:
        """Safely get text content of a child element."""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return default

    def _is_success(self, result: str) -> bool:
        """Check if result code indicates success."""
        return result == '000'

    def _error_message(self, result: str, message: str = '') -> str:
        """Build a human-readable error message from result code."""
        desc = RESULT_CODES.get(result, 'Unknown error')
        if message:
            return f'{desc} ({result}): {message}'
        return f'{desc} ({result})'

    # ---- Public API methods ----

    def create_payment(
        self,
        amount: int,
        currency: str,
        card_data: Dict[str, str],
        donor_data: Dict[str, str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a charge via CreditGuard XML API.

        Args:
            amount: Amount in smallest currency unit (agorot/cents)
            currency: Currency code (ILS, USD, EUR, GBP)
            card_data: Dict with keys: card_number, expiration (MMYY), cvv
            donor_data: Optional dict with keys: name, email, id_number, phone
            **kwargs:
                installments (int): Number of installments (default 1)
                transaction_type (str): 'Debit', 'Credit', 'Authorize' (default 'Debit')
                credit_type (str): 'RegularCredit', 'Payments', etc. (default 'RegularCredit')

        Returns:
            Dict with: success, transaction_id, confirmation, token, card_mask,
                        card_brand, error, raw_response
        """
        donor_data = donor_data or {}
        installments = kwargs.get('installments', 1)
        transaction_type = kwargs.get('transaction_type', 'Debit')
        credit_type = kwargs.get('credit_type', 'RegularCredit')

        if installments > 1:
            credit_type = 'Payments'

        # Calculate installment amounts
        first_payment = amount
        periodical_payment = 0
        if installments > 1:
            periodical_payment = amount // installments
            first_payment = amount - (periodical_payment * (installments - 1))

        deal_params = {
            'cardNo': card_data.get('card_number', ''),
            'cardExpiration': card_data.get('expiration', ''),
            'cvv': card_data.get('cvv', ''),
            'total': str(amount),
            'transactionType': transaction_type,
            'creditType': credit_type,
            'currency': CURRENCY_MAP.get(currency.upper(), 'ILS'),
            'transactionCode': 'Phone',
            'validation': 'TxnSetup',
            'numberOfPayments': str(installments),
            'firstPayment': str(first_payment),
            'periodicalPayment': str(periodical_payment),
            'id': donor_data.get('id_number', ''),
            'uniqueid': donor_data.get('email', ''),
        }

        xml_body = self._build_xml('doDeal', deal_params)

        try:
            response_text = self._post_xml(xml_body)
            parsed = self._parse_response(response_text, 'doDeal')

            result_code = parsed.get('result', '999')
            if self._is_success(result_code):
                logger.info(
                    f'CreditGuard payment approved: tranId={parsed.get("tranId")}, '
                    f'auth={parsed.get("authNumber")}, amount={amount} {currency}'
                )
                return {
                    'success': True,
                    'transaction_id': parsed.get('tranId'),
                    'confirmation': parsed.get('authNumber'),
                    'token': parsed.get('cardToken'),
                    'card_mask': parsed.get('cardMask'),
                    'card_brand': parsed.get('cardBrand'),
                    'processor': self.code,
                    'raw_response': parsed,
                }
            else:
                error_msg = self._error_message(
                    result_code,
                    parsed.get('userMessage') or parsed.get('message', '')
                )
                logger.warning(f'CreditGuard payment declined: {error_msg}')
                return {
                    'success': False,
                    'error': error_msg,
                    'result_code': result_code,
                    'processor': self.code,
                    'raw_response': parsed,
                }

        except requests.RequestException as e:
            logger.error(f'CreditGuard HTTP error: {e}')
            return {
                'success': False,
                'error': f'Connection error: {e}',
                'processor': self.code,
            }
        except Exception as e:
            logger.error(f'CreditGuard unexpected error: {e}')
            return {
                'success': False,
                'error': f'Unexpected error: {e}',
                'processor': self.code,
            }

    def get_client_config(self) -> Dict[str, Any]:
        """
        Get frontend configuration for CreditGuard.

        CreditGuard uses server-to-server XML API, so the client config
        provides metadata about accepted cards and currencies.
        """
        return {
            'type': 'server_to_server',
            'processor': self.code,
            'name': self.name,
            'supported_currencies': self.SUPPORTED_CURRENCIES,
            'sandbox': self.config.get('sandbox', True),
        }

    def refund(
        self,
        transaction_id: str,
        amount: int = None,
        auth_number: str = None,
        currency: str = 'ILS',
    ) -> Dict[str, Any]:
        """
        Process a refund (credit transaction).

        Args:
            transaction_id: Original transaction ID (tranId) - used for logging/tracking
            amount: Refund amount in smallest currency unit. Required.
            auth_number: Original authorization number. Required for CreditGuard refunds.
            currency: Currency code (default ILS)

        Returns:
            Dict with: success, transaction_id (of refund), confirmation, error
        """
        if not amount:
            return {
                'success': False,
                'error': 'Refund amount is required for CreditGuard',
                'processor': self.code,
            }

        if not auth_number:
            return {
                'success': False,
                'error': 'Original auth_number is required for CreditGuard refunds',
                'processor': self.code,
            }

        deal_params = {
            'transactionType': 'Credit',
            'creditType': 'RegularCredit',
            'total': str(amount),
            'currency': CURRENCY_MAP.get(currency.upper(), 'ILS'),
            'authNumber': auth_number,
            'transactionCode': 'Phone',
            'validation': 'TxnSetup',
        }

        xml_body = self._build_xml('doDeal', deal_params)

        try:
            response_text = self._post_xml(xml_body)
            parsed = self._parse_response(response_text, 'doDeal')

            result_code = parsed.get('result', '999')
            if self._is_success(result_code):
                logger.info(
                    f'CreditGuard refund approved: tranId={parsed.get("tranId")}, '
                    f'original_auth={auth_number}, amount={amount} {currency}'
                )
                return {
                    'success': True,
                    'transaction_id': parsed.get('tranId'),
                    'confirmation': parsed.get('authNumber'),
                    'amount_refunded': amount,
                    'processor': self.code,
                    'raw_response': parsed,
                }
            else:
                error_msg = self._error_message(
                    result_code,
                    parsed.get('userMessage') or parsed.get('message', '')
                )
                logger.warning(f'CreditGuard refund declined: {error_msg}')
                return {
                    'success': False,
                    'error': error_msg,
                    'result_code': result_code,
                    'processor': self.code,
                    'raw_response': parsed,
                }

        except requests.RequestException as e:
            logger.error(f'CreditGuard refund HTTP error: {e}')
            return {
                'success': False,
                'error': f'Connection error: {e}',
                'processor': self.code,
            }

    def charge_token(
        self,
        token: str,
        amount: int,
        currency: str,
        donor_data: Dict[str, str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Charge a saved card token (recurring payment).

        Args:
            token: Card token from previous transaction (cardToken)
            amount: Amount in smallest currency unit
            currency: Currency code
            donor_data: Optional dict with donor info
            **kwargs:
                installments (int): Number of installments (default 1)

        Returns:
            Dict with: success, transaction_id, confirmation, error
        """
        donor_data = donor_data or {}
        installments = kwargs.get('installments', 1)
        credit_type = 'RegularCredit'

        first_payment = amount
        periodical_payment = 0
        if installments > 1:
            credit_type = 'Payments'
            periodical_payment = amount // installments
            first_payment = amount - (periodical_payment * (installments - 1))

        deal_params = {
            'cardToken': token,
            'total': str(amount),
            'transactionType': 'Debit',
            'creditType': credit_type,
            'currency': CURRENCY_MAP.get(currency.upper(), 'ILS'),
            'transactionCode': 'Phone',
            'validation': 'TxnSetup',
            'numberOfPayments': str(installments),
            'firstPayment': str(first_payment),
            'periodicalPayment': str(periodical_payment),
            'id': donor_data.get('id_number', ''),
            'uniqueid': donor_data.get('email', ''),
        }

        xml_body = self._build_xml('doDeal', deal_params)

        try:
            response_text = self._post_xml(xml_body)
            parsed = self._parse_response(response_text, 'doDeal')

            result_code = parsed.get('result', '999')
            if self._is_success(result_code):
                logger.info(
                    f'CreditGuard token charge approved: tranId={parsed.get("tranId")}, '
                    f'amount={amount} {currency}'
                )
                return {
                    'success': True,
                    'transaction_id': parsed.get('tranId'),
                    'confirmation': parsed.get('authNumber'),
                    'token': parsed.get('cardToken'),
                    'card_mask': parsed.get('cardMask'),
                    'card_brand': parsed.get('cardBrand'),
                    'processor': self.code,
                    'raw_response': parsed,
                }
            else:
                error_msg = self._error_message(
                    result_code,
                    parsed.get('userMessage') or parsed.get('message', '')
                )
                logger.warning(f'CreditGuard token charge declined: {error_msg}')
                return {
                    'success': False,
                    'error': error_msg,
                    'result_code': result_code,
                    'processor': self.code,
                    'raw_response': parsed,
                }

        except requests.RequestException as e:
            logger.error(f'CreditGuard token charge HTTP error: {e}')
            return {
                'success': False,
                'error': f'Connection error: {e}',
                'processor': self.code,
            }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Retrieve transaction details using inquireTransactions command.

        Args:
            transaction_id: The CreditGuard tranId

        Returns:
            Dict with: success, transaction_id, amount, currency, status, raw_response
        """
        params = {
            'queryName': 'mpiTransaction',
            'tranId': transaction_id,
        }

        xml_body = self._build_xml('inquireTransactions', params)

        try:
            response_text = self._post_xml(xml_body)
            parsed = self._parse_response(response_text, 'inquireTransactions')

            result_code = parsed.get('result', '999')
            if self._is_success(result_code):
                return {
                    'success': True,
                    'transaction_id': parsed.get('tranId', transaction_id),
                    'amount': parsed.get('total'),
                    'currency': parsed.get('currency'),
                    'auth_number': parsed.get('authNumber'),
                    'card_mask': parsed.get('cardMask'),
                    'card_brand': parsed.get('cardBrand'),
                    'processor': self.code,
                    'raw_response': parsed,
                }
            else:
                return {
                    'success': False,
                    'error': self._error_message(
                        result_code,
                        parsed.get('message', '')
                    ),
                    'processor': self.code,
                    'raw_response': parsed,
                }

        except requests.RequestException as e:
            logger.error(f'CreditGuard inquiry HTTP error: {e}')
            return {
                'success': False,
                'error': f'Connection error: {e}',
                'processor': self.code,
            }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test API connectivity by sending a zero-amount validation request.

        Returns:
            Dict with: success, message
        """
        if not self._get_terminal() or not self._get_username() or not self._get_password():
            return {
                'success': False,
                'message': 'Missing credentials: terminal_number, username, and password are required',
            }

        # Send a minimal doDeal with Authorize type and zero amount to validate credentials
        deal_params = {
            'total': '100',
            'transactionType': 'Authorize',
            'creditType': 'RegularCredit',
            'currency': 'ILS',
            'transactionCode': 'Phone',
            'validation': 'TxnSetup',
            'cardNo': '4580458045804580',
            'cardExpiration': '1230',
            'cvv': '123',
        }

        xml_body = self._build_xml('doDeal', deal_params)

        try:
            response_text = self._post_xml(xml_body)
            # If we get a parseable response, the connection works
            parsed = self._parse_response(response_text, 'doDeal')
            result_code = parsed.get('result', '999')

            # Even a declined card means the API connection works
            if result_code in ('000', '001', '002', '003', '004', '006', '012', '036'):
                return {
                    'success': True,
                    'message': f'Connection successful. API responded with code {result_code}.',
                }
            else:
                return {
                    'success': False,
                    'message': f'API responded with unexpected code {result_code}: {parsed.get("message", "")}',
                }

        except requests.RequestException as e:
            return {
                'success': False,
                'message': f'Connection failed: {e}',
            }

    def supports_currency(self, currency: str) -> bool:
        """Check if currency is supported."""
        return currency.upper() in self.SUPPORTED_CURRENCIES

    def estimate_fee(self, amount: int, currency: str) -> int:
        """
        Estimate CreditGuard processing fee.

        Typical rate: ~1.5% for ILS domestic, ~2.5% for international.
        Actual rates depend on merchant agreement.
        """
        currency = currency.upper()
        if currency == 'ILS':
            return int(amount * 0.015)
        else:
            return int(amount * 0.025)
