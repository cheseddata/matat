"""
Matbia Charity Card Processor.

REST API integration for Matbia charity card payments.
Matbia is a Jewish charity card platform with physical NFC cards.

API Docs: https://developers.matbia.org
"""
import requests
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class MatbiaProcessor(BasePaymentProcessor):
    """
    Matbia charity card payment processor.

    Donors use physical NFC charity cards (like credit cards for tzedakah).
    Supports one-time charges, recurring schedules, and preauthorization.

    Config required:
    - api_key: Matbia API key
    - org_handle: Your organization's Matbia handle
    OR
    - org_tax_id + org_name + org_email

    Optional:
    - sandbox: True for testing (default False)
    """

    PRODUCTION_URL = 'https://api.matbia.org'
    SANDBOX_URL = 'https://sandbox.api.matbia.org'

    # Standard nonprofit processing fee
    FEE_PERCENTAGE = Decimal('0.029')  # 2.9%
    FEE_FIXED_CENTS = 30  # $0.30

    @property
    def code(self) -> str:
        return 'matbia'

    @property
    def display_name(self) -> str:
        return 'Matbia'

    @property
    def processor_type(self) -> str:
        """DAF/charity card processor type."""
        return 'daf'

    def initialize(self) -> bool:
        """Validate configuration."""
        if not self.config.get('api_key'):
            logger.error("Matbia: Missing api_key")
            return False

        # Need org_handle OR (org_tax_id + org_name + org_email)
        if not self.config.get('org_handle'):
            required_alt = ['org_tax_id', 'org_name', 'org_email']
            if not all(self.config.get(k) for k in required_alt):
                logger.error("Matbia: Need org_handle or (org_tax_id + org_name + org_email)")
                return False

        self._initialized = True
        return True

    @property
    def _base_url(self) -> str:
        """Get base URL based on sandbox mode."""
        if self.config.get('sandbox', False):
            return self.SANDBOX_URL
        return self.PRODUCTION_URL

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers."""
        return {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {self.config['api_key']}"
        }

    def _get_org_identification(self) -> Dict[str, Any]:
        """Get organization identification fields for API calls."""
        if self.config.get('org_handle'):
            return {'orgUserHandle': self.config['org_handle']}
        else:
            return {
                'orgTaxId': self.config['org_tax_id'],
                'orgName': self.config['org_name'],
                'orgEmail': self.config['org_email']
            }

    def create_payment(
        self,
        amount_cents: int,
        currency: str,
        donor_email: str,
        donor_name: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Process a one-time Matbia card charge.

        Metadata must include:
        - card_number: Matbia card number

        Optional:
        - note: Donation note/purpose
        """
        metadata = metadata or {}

        if not metadata.get('card_number'):
            return {
                'success': False,
                'error': 'Matbia card number required'
            }

        # Build request body
        body = {
            'amount': amount_cents / 100,  # API expects dollars
            'cardNumber': metadata['card_number'],
            'donorEmail': donor_email,
            'donorName': donor_name,
            **self._get_org_identification()
        }

        if metadata.get('note'):
            body['note'] = metadata['note']

        try:
            response = requests.post(
                f'{self._base_url}/v1/Matbia/Charge',
                json=body,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                return {
                    'success': True,
                    'transaction_id': data.get('transactionId'),
                    'confirmation_number': data.get('confirmationNumber'),
                    'amount_cents': amount_cents,
                    'currency': currency,
                    'is_daf': True,
                    'daf_provider': 'Matbia'
                }
            else:
                data = response.json() if response.content else {}
                return {
                    'success': False,
                    'error': data.get('message', f'HTTP {response.status_code}'),
                    'status_code': response.status_code
                }

        except requests.RequestException as e:
            logger.error(f"Matbia charge error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def preauthorize(
        self,
        card_number: str,
        amount_cents: int = None
    ) -> Dict[str, Any]:
        """
        Preauthorize/validate a Matbia card.

        Verifies the card is valid before charging.

        Args:
            card_number: Matbia card number
            amount_cents: Optional amount to verify balance (in cents)
        """
        body = {
            'cardNumber': card_number,
            **self._get_org_identification()
        }

        if amount_cents:
            body['amount'] = amount_cents / 100

        try:
            response = requests.post(
                f'{self._base_url}/v1/Matbia/Preauthorization',
                json=body,
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'valid': True,
                    'available_balance': data.get('availableBalance'),
                    'data': data
                }
            else:
                data = response.json() if response.content else {}
                return {
                    'valid': False,
                    'error': data.get('message', 'Card validation failed')
                }

        except requests.RequestException as e:
            logger.error(f"Matbia preauthorize error: {e}")
            return {
                'valid': False,
                'error': str(e)
            }

    def schedule_recurring(
        self,
        card_number: str,
        amount_cents: int,
        frequency: str,
        donor_email: str,
        donor_name: str,
        start_date: str = None,
        end_date: str = None,
        note: str = None
    ) -> Dict[str, Any]:
        """
        Set up a recurring donation schedule.

        Args:
            card_number: Matbia card number
            amount_cents: Amount per charge
            frequency: weekly|biweekly|monthly|quarterly|annually
            donor_email: Donor email
            donor_name: Donor name
            start_date: Start date (ISO format)
            end_date: End date (ISO format, optional)
            note: Donation note
        """
        body = {
            'cardNumber': card_number,
            'amount': amount_cents / 100,
            'frequency': frequency,
            'donorEmail': donor_email,
            'donorName': donor_name,
            **self._get_org_identification()
        }

        if start_date:
            body['startDate'] = start_date
        if end_date:
            body['endDate'] = end_date
        if note:
            body['note'] = note

        try:
            response = requests.post(
                f'{self._base_url}/v1/Matbia/Schedule',
                json=body,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code in (200, 201):
                data = response.json()

                return {
                    'success': True,
                    'schedule_id': data.get('scheduleId'),
                    'recurring_id': data.get('scheduleId'),
                    'frequency': frequency,
                    'amount_cents': amount_cents,
                    'is_daf': True,
                    'daf_provider': 'Matbia'
                }
            else:
                data = response.json() if response.content else {}
                return {
                    'success': False,
                    'error': data.get('message', f'HTTP {response.status_code}')
                }

        except requests.RequestException as e:
            logger.error(f"Matbia schedule error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_client_config(self) -> Dict[str, Any]:
        """
        Return config for frontend form rendering.

        Matbia uses a server-side API with card number input.
        """
        return {
            'type': 'form',
            'processor': 'matbia',
            'display_name': 'Matbia',
            'description': 'Pay with your Matbia charity card',
            'fields': [
                {
                    'name': 'card_number',
                    'type': 'text',
                    'label': 'Matbia Card Number',
                    'required': True,
                    'placeholder': 'Enter your Matbia card number'
                }
            ],
            'supports_recurring': True,
            'recurring_frequencies': ['weekly', 'biweekly', 'monthly', 'quarterly', 'annually'],
            'sandbox': self.config.get('sandbox', False)
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process Matbia webhook callback.

        Matbia may send transaction status updates.
        """
        import json

        try:
            data = json.loads(request_data)

            return {
                'event_type': data.get('eventType', 'transaction_update'),
                'transaction_id': data.get('transactionId'),
                'amount_cents': int(data.get('amount', 0) * 100),
                'currency': 'USD',
                'status': data.get('status'),
                'donor_email': data.get('donorEmail'),
                'donor_name': data.get('donorName'),
                'raw_data': data
            }

        except json.JSONDecodeError as e:
            logger.error(f"Matbia webhook parse error: {e}")
            return {
                'event_type': 'error',
                'error': str(e)
            }

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Matbia refunds are typically handled through their dashboard.

        Contact Matbia support for API refund capability.
        """
        logger.warning(f"Matbia refund requested for {transaction_id} - manual process required")
        return {
            'success': False,
            'error': 'Matbia refunds require manual processing through dashboard'
        }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get transaction details.

        Note: Check Matbia API docs for exact endpoint.
        """
        try:
            response = requests.get(
                f'{self._base_url}/v1/Matbia/Transaction/{transaction_id}',
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code == 200:
                return {
                    'success': True,
                    'transaction_id': transaction_id,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'Transaction not found (HTTP {response.status_code})'
                }

        except requests.RequestException as e:
            logger.error(f"Matbia get_transaction error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def cancel_recurring(self, schedule_id: str) -> Dict[str, Any]:
        """
        Cancel a recurring donation schedule.
        """
        try:
            response = requests.delete(
                f'{self._base_url}/v1/Matbia/Schedule/{schedule_id}',
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code in (200, 204):
                return {
                    'success': True,
                    'message': 'Schedule cancelled'
                }
            else:
                data = response.json() if response.content else {}
                return {
                    'success': False,
                    'error': data.get('message', f'HTTP {response.status_code}')
                }

        except requests.RequestException as e:
            logger.error(f"Matbia cancel_recurring error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_recurring_status(self, schedule_id: str) -> Dict[str, Any]:
        """Get status of a recurring schedule."""
        try:
            response = requests.get(
                f'{self._base_url}/v1/Matbia/Schedule/{schedule_id}',
                headers=self._get_headers(),
                timeout=15
            )

            if response.status_code == 200:
                return {
                    'success': True,
                    'schedule_id': schedule_id,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'Schedule not found (HTTP {response.status_code})'
                }

        except requests.RequestException as e:
            logger.error(f"Matbia get_recurring_status error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def supports_currency(self, currency: str) -> bool:
        """Matbia primarily supports USD."""
        return currency.upper() == 'USD'

    def supports_country(self, country_code: str) -> bool:
        """Matbia is US-based."""
        return country_code.upper() == 'US'

    def supports_recurring(self) -> bool:
        """Matbia supports recurring via Schedule endpoint."""
        return True

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """
        Estimate processing fee (2.9% + $0.30).
        """
        percentage_fee = int(amount_cents * self.FEE_PERCENTAGE)
        return percentage_fee + self.FEE_FIXED_CENTS
