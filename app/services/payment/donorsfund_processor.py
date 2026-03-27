"""
The Donors Fund DAF Processor.

REST API integration for The Donors Fund donor-advised fund.
Supports two authentication methods: username+PIN or card+CVV.

API Docs: https://thedonorsfund.org/api-documentation
"""
import requests
import logging
from typing import Dict, Any, Optional
from decimal import Decimal

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class DonorsFundProcessor(BasePaymentProcessor):
    """
    The Donors Fund DAF payment processor.

    Donors authenticate with either:
    - Username + 4-digit PIN
    - 16-digit giving card + 3-digit CVV

    Config required:
    - validation_token: Private API token (from The Donors Fund)
    - account_number: Your charity account number
    - tax_id: Your charity tax ID
    - sandbox: True for testing (default False)
    """

    # Public API keys (same for all integrators)
    SANDBOX_API_KEY = '3Q1i2KzHmUCiPDr8gCtiRQB6ZtIJBVjEKwSUGwFdtfvw'
    PRODUCTION_API_KEY = 'CXtaaW9xqUafyffApPbfVQD0MmLhdprESvor9vi2GNLQ'

    SANDBOX_URL = 'https://api.tdfcharitable.org/thedonorsfund/integration'
    PRODUCTION_URL = 'https://api.thedonorsfund.org/thedonorsfund/integration'

    # Fee: 2.9%
    FEE_PERCENTAGE = Decimal('0.029')

    @property
    def code(self) -> str:
        return 'donors_fund'

    @property
    def display_name(self) -> str:
        return 'The Donors Fund'

    @property
    def processor_type(self) -> str:
        """DAF processor type for categorization."""
        return 'daf'

    def initialize(self) -> bool:
        """Validate configuration."""
        required = ['validation_token']
        if not all(self.config.get(k) for k in required):
            logger.error("DonorsFund: Missing validation_token")
            return False

        # Need either account_number or tax_id
        if not self.config.get('account_number') and not self.config.get('tax_id'):
            logger.error("DonorsFund: Need either account_number or tax_id")
            return False

        self._initialized = True
        return True

    @property
    def _base_url(self) -> str:
        """Get base URL based on sandbox mode."""
        if self.config.get('sandbox', False):
            return self.SANDBOX_URL
        return self.PRODUCTION_URL

    @property
    def _api_key(self) -> str:
        """Get API key based on sandbox mode."""
        if self.config.get('sandbox', False):
            return self.SANDBOX_API_KEY
        return self.PRODUCTION_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with both required keys."""
        return {
            'Content-Type': 'application/json',
            'Api-Key': self._api_key,
            'Validation-Token': self.config['validation_token']
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
        Create a grant from donor's DAF account.

        Metadata must include authentication credentials:
        Either:
        - username + pin (4 digits)
        Or:
        - card_number (16 digits) + cvv (3 digits)

        Optional:
        - is_recurring: True for recurring grants
        - recurring_type: weekly|biweekly|monthly|bimonthly|quarterly|semiannually|annually
        - start_date: Start date for recurring
        - purpose: Grant purpose
        - purpose_note: Purpose details
        """
        metadata = metadata or {}

        # Build request body
        body = {
            'amount': amount_cents / 100  # API expects dollars, not cents
        }

        # Charity identification
        if self.config.get('account_number'):
            body['accountNumber'] = int(self.config['account_number'])
        if self.config.get('tax_id'):
            body['taxId'] = self.config['tax_id']

        # Donor authentication - either username+pin OR card+cvv
        if metadata.get('username') and metadata.get('pin'):
            body['userName'] = metadata['username']
            body['pin'] = int(metadata['pin'])
        elif metadata.get('card_number') and metadata.get('cvv'):
            body['cardNumber'] = metadata['card_number']
            body['cvv'] = metadata['cvv']
        else:
            return {
                'success': False,
                'error': 'Missing donor authentication (username+pin or card+cvv)'
            }

        # Recurring grant options
        if metadata.get('is_recurring'):
            body['isRecurringGrant'] = True
            if metadata.get('recurring_type'):
                body['recurringType'] = metadata['recurring_type']
            if metadata.get('start_date'):
                body['startDate'] = metadata['start_date']
        else:
            body['isRecurringGrant'] = False

        # Purpose fields
        if metadata.get('purpose'):
            body['purpose'] = metadata['purpose']
        if metadata.get('purpose_note'):
            body['purposeNote'] = metadata['purpose_note']

        # Optional merchant info
        if metadata.get('phone'):
            body['merchantPhoneNumber'] = int(metadata['phone'].replace('-', '').replace(' ', ''))
        if metadata.get('merchant_id'):
            body['merchantID'] = metadata['merchant_id']

        try:
            response = requests.post(
                f'{self._base_url}/create',
                json=body,
                headers=self._get_headers(),
                timeout=30
            )

            data = response.json()

            # Note: statusCode is always 200, check errorCode instead
            if data.get('errorCode', 0) == 0:
                return {
                    'success': True,
                    'transaction_id': data.get('confirmationNumber'),
                    'confirmation_number': data.get('confirmationNumber'),
                    'amount_cents': amount_cents,
                    'currency': currency,
                    'is_daf': True,
                    'daf_provider': 'The Donors Fund'
                }
            else:
                return {
                    'success': False,
                    'error': data.get('error', 'Unknown error'),
                    'error_code': data.get('errorCode')
                }

        except requests.RequestException as e:
            logger.error(f"DonorsFund create_payment error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def validate_card(self, card_number: str, cvv: str) -> Dict[str, Any]:
        """
        Pre-validate a giving card before creating a grant.

        Args:
            card_number: 16-digit giving card number
            cvv: 3-digit CVV

        Returns:
            Dict with validation result
        """
        try:
            response = requests.post(
                f'{self._base_url}/validate',
                json={
                    'cardNumber': card_number,
                    'cvv': cvv
                },
                headers=self._get_headers(),
                timeout=15
            )

            data = response.json()

            if data.get('errorCode', 0) == 0:
                return {
                    'valid': True,
                    'error': None
                }
            else:
                return {
                    'valid': False,
                    'error': data.get('error', 'Invalid card')
                }

        except requests.RequestException as e:
            logger.error(f"DonorsFund validate_card error: {e}")
            return {
                'valid': False,
                'error': str(e)
            }

    def get_client_config(self) -> Dict[str, Any]:
        """
        Return config for frontend form rendering.

        The Donors Fund uses a server-side API, not a frontend widget.
        Frontend shows form with two tabs: username+pin or card+cvv.
        """
        return {
            'type': 'form',
            'processor': 'donors_fund',
            'display_name': 'The Donors Fund',
            'auth_methods': [
                {
                    'type': 'username_pin',
                    'label': 'Username & PIN',
                    'fields': [
                        {'name': 'username', 'type': 'text', 'label': 'Username', 'required': True},
                        {'name': 'pin', 'type': 'password', 'label': '4-Digit PIN', 'required': True, 'maxlength': 4}
                    ]
                },
                {
                    'type': 'card_cvv',
                    'label': 'Giving Card',
                    'fields': [
                        {'name': 'card_number', 'type': 'text', 'label': 'Card Number', 'required': True, 'maxlength': 16},
                        {'name': 'cvv', 'type': 'password', 'label': 'CVV', 'required': True, 'maxlength': 3}
                    ]
                }
            ],
            'sandbox': self.config.get('sandbox', False)
        }

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        The Donors Fund doesn't send webhooks.
        Transactions are synchronous via the /create endpoint.
        """
        return {
            'event_type': 'not_supported',
            'error': 'The Donors Fund does not use webhooks'
        }

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Cancel a grant using PUT /cancel.

        Note: This is a full cancellation, not partial refund.
        """
        try:
            response = requests.put(
                f'{self._base_url}/cancel',
                json={'transactionId': transaction_id},
                headers=self._get_headers(),
                timeout=15
            )

            data = response.json()

            if data.get('errorCode', 0) == 0:
                return {
                    'success': True,
                    'refund_id': transaction_id,
                    'message': 'Grant cancelled'
                }
            else:
                return {
                    'success': False,
                    'error': data.get('error', 'Failed to cancel grant')
                }

        except requests.RequestException as e:
            logger.error(f"DonorsFund cancel error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get grant details using GET /grant/details/{confirmationNumber}.
        """
        try:
            response = requests.get(
                f'{self._base_url}/grant/details/{transaction_id}',
                headers=self._get_headers(),
                timeout=15
            )

            data = response.json()

            if data.get('errorCode', 0) == 0:
                return {
                    'success': True,
                    'transaction_id': transaction_id,
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'error': data.get('error', 'Grant not found')
                }

        except requests.RequestException as e:
            logger.error(f"DonorsFund get_transaction error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_charity_accounts(self, tax_id: str) -> Dict[str, Any]:
        """
        Look up all account numbers for a tax ID.

        Useful when a charity has multiple Donors Fund accounts.
        """
        try:
            response = requests.get(
                f'{self._base_url}/charity/account-numbers/{tax_id}',
                headers=self._get_headers(),
                timeout=15
            )

            data = response.json()

            if data.get('errorCode', 0) == 0:
                return {
                    'success': True,
                    'accounts': data.get('accounts', [])
                }
            else:
                return {
                    'success': False,
                    'error': data.get('error', 'Tax ID not found')
                }

        except requests.RequestException as e:
            logger.error(f"DonorsFund get_charity_accounts error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def supports_currency(self, currency: str) -> bool:
        """The Donors Fund only supports USD."""
        return currency.upper() == 'USD'

    def supports_country(self, country_code: str) -> bool:
        """The Donors Fund is US-based."""
        return country_code.upper() == 'US'

    def supports_recurring(self) -> bool:
        """Built-in recurring support via isRecurringGrant."""
        return True

    def cancel_recurring(self, recurring_id: str) -> Dict[str, Any]:
        """Cancel recurring grant (same as regular cancel)."""
        return self.refund(recurring_id)

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """
        Estimate processing fee (2.9%).
        """
        return int(amount_cents * self.FEE_PERCENTAGE)
