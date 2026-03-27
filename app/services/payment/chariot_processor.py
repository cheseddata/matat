"""
Chariot / DAFpay Universal DAF Processor.

One button covers 1,151+ DAF providers including:
- The Donors Fund
- OJC Fund
- Jewish Communal Fund (JCF)
- Combined Jewish Philanthropies (CJP)
- Fidelity Charitable
- Schwab Charitable
- All Jewish Federation DAFs
- And 1,100+ more

API Docs: https://docs.givechariot.com
"""
import requests
import hmac
import hashlib
import base64
import json
import logging
from typing import Dict, Any, Optional

from .base import BasePaymentProcessor

logger = logging.getLogger(__name__)


class ChariotProcessor(BasePaymentProcessor):
    """
    Chariot/DAFpay universal DAF payment processor.

    Frontend: DAFpay web component button
    Backend: Webhook receives grant confirmations

    Config required:
    - api_key: Chariot API key
    - connect_id: Connect ID (CID) for DAFpay button
    - ein: Your nonprofit's EIN (for registration)

    Optional:
    - sandbox: True for testing (default False)
    - webhook_secret: For HMAC verification (same as api_key if not set)
    """

    PRODUCTION_URL = 'https://api.givechariot.com'
    SANDBOX_URL = 'https://sandboxapi.givechariot.com'

    # Fee: 2.9%
    FEE_PERCENTAGE = 0.029

    @property
    def code(self) -> str:
        return 'chariot'

    @property
    def display_name(self) -> str:
        return 'DAFpay (Chariot)'

    @property
    def processor_type(self) -> str:
        """DAF aggregator covering all providers."""
        return 'daf_aggregator'

    def initialize(self) -> bool:
        """Validate configuration."""
        if not self.config.get('api_key'):
            logger.error("Chariot: Missing api_key")
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

    def register_nonprofit(self, ein: str = None) -> Dict[str, Any]:
        """
        Register nonprofit with Chariot by EIN.

        This should be done once during setup.

        Args:
            ein: EIN without hyphens (e.g., '123456789')

        Returns:
            201 for new registration, 200 for existing
        """
        nonprofit_ein = ein or self.config.get('ein')

        if not nonprofit_ein:
            return {
                'success': False,
                'error': 'EIN required for registration'
            }

        try:
            response = requests.post(
                f'{self._base_url}/nonprofits',
                json={'ein': nonprofit_ein.replace('-', '')},
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code in (200, 201):
                data = response.json()
                return {
                    'success': True,
                    'nonprofit_id': data.get('id'),
                    'is_new': response.status_code == 201,
                    'data': data
                }
            else:
                data = response.json() if response.content else {}
                return {
                    'success': False,
                    'error': data.get('message', f'HTTP {response.status_code}')
                }

        except requests.RequestException as e:
            logger.error(f"Chariot register_nonprofit error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def create_connect(self, nonprofit_id: str = None) -> Dict[str, Any]:
        """
        Create a Connect instance (CID) for the DAFpay button.

        The Connect ID is used to initialize the frontend component.

        Args:
            nonprofit_id: Nonprofit ID from registration (or auto-detect)
        """
        try:
            body = {}
            if nonprofit_id:
                body['nonprofitId'] = nonprofit_id

            response = requests.post(
                f'{self._base_url}/connects',
                json=body,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code in (200, 201):
                data = response.json()
                return {
                    'success': True,
                    'connect_id': data.get('id'),
                    'data': data
                }
            else:
                data = response.json() if response.content else {}
                return {
                    'success': False,
                    'error': data.get('message', f'HTTP {response.status_code}')
                }

        except requests.RequestException as e:
            logger.error(f"Chariot create_connect error: {e}")
            return {
                'success': False,
                'error': str(e)
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
        DAFpay payments are initiated by the frontend widget.

        This method returns the configuration for the DAFpay button.
        The actual payment happens client-side through the DAFpay popup.
        """
        metadata = metadata or {}

        return {
            'success': True,
            'type': 'widget',
            'widget_type': 'dafpay',
            'connect_id': self.config.get('connect_id'),
            'amount_cents': amount_cents,
            'currency': currency,
            'donor_email': donor_email,
            'donor_name': donor_name,
            'tracking_id': metadata.get('tracking_id'),
            'message': 'Use DAFpay button to complete donation'
        }

    def get_client_config(self) -> Dict[str, Any]:
        """
        Return config for frontend DAFpay button.

        The DAFpay button is a web component that handles the entire
        DAF authentication and grant flow.
        """
        connect_id = self.config.get('connect_id')

        if not connect_id:
            logger.warning("Chariot: connect_id not configured. Run create_connect() first.")

        return {
            'type': 'widget',
            'widget_type': 'dafpay',
            'processor': 'chariot',
            'display_name': 'DAFpay',
            'description': 'Pay from your Donor-Advised Fund',
            'connect_id': connect_id,
            'sandbox': self.config.get('sandbox', False),
            # Frontend should include Chariot script and render DAFpay button
            'script_url': 'https://cdn.givechariot.com/dafpay.js',
            'supported_providers': [
                'The Donors Fund',
                'OJC Fund',
                'Jewish Communal Fund',
                'Combined Jewish Philanthropies',
                'Fidelity Charitable',
                'Schwab Charitable',
                'Vanguard Charitable',
                'National Philanthropic Trust',
                '1,143+ more providers'
            ]
        }

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> bool:
        """
        Verify Chariot webhook signature.

        HMAC-SHA256 using api_key as key, payload as message, Base64 encoded.

        Args:
            payload: Raw request body
            signature: Signature from header

        Returns:
            True if signature is valid
        """
        secret = self.config.get('webhook_secret') or self.config.get('api_key')

        if not secret:
            logger.error("Chariot: No api_key for signature verification")
            return False

        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).digest()

        expected_b64 = base64.b64encode(expected).decode('utf-8')

        return hmac.compare_digest(expected_b64, signature)

    def verify_webhook_origin(
        self,
        request_data: bytes,
        headers: Dict[str, str],
        remote_ip: str = None
    ) -> bool:
        """
        Verify webhook is from Chariot using HMAC signature.
        """
        # Get signature from header (check common header names)
        signature = (
            headers.get('X-Chariot-Signature') or
            headers.get('x-chariot-signature') or
            headers.get('X-Signature') or
            headers.get('x-signature')
        )

        if not signature:
            logger.warning("Chariot webhook: No signature header found")
            return False

        return self.verify_webhook_signature(request_data, signature)

    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process Chariot webhook for grant status updates.

        Webhook payload includes:
        - grant_id: Chariot's grant ID
        - tracking_id: Your tracking ID (if provided)
        - amount: Grant amount
        - daf_provider: Name of the DAF provider used
        - status: Grant status
        - donor info (if available)
        """
        try:
            data = json.loads(request_data)

            # Normalize the event data
            event_type = data.get('event_type', 'grant_received')
            status = data.get('status', 'completed')

            # Map status to event type
            if status in ('completed', 'success', 'approved'):
                event_type = 'payment_succeeded'
            elif status in ('failed', 'declined', 'rejected'):
                event_type = 'payment_failed'
            elif status in ('pending', 'processing'):
                event_type = 'payment_pending'
            elif status in ('cancelled', 'canceled'):
                event_type = 'payment_cancelled'

            # Extract amount (handle both cents and dollars)
            amount = data.get('amount', 0)
            if isinstance(amount, float) and amount < 10000:
                # Probably in dollars, convert to cents
                amount_cents = int(amount * 100)
            else:
                amount_cents = int(amount)

            return {
                'event_type': event_type,
                'transaction_id': data.get('grant_id') or data.get('id'),
                'tracking_id': data.get('tracking_id'),
                'external_grant_id': data.get('external_grant_id'),
                'amount_cents': amount_cents,
                'currency': data.get('currency', 'USD'),
                'daf_provider': data.get('daf_provider') or data.get('provider_name'),
                'donor_email': data.get('donor', {}).get('email') or data.get('donor_email'),
                'donor_name': data.get('donor', {}).get('name') or data.get('donor_name'),
                'is_daf': True,
                'status': status,
                'raw_data': data
            }

        except json.JSONDecodeError as e:
            logger.error(f"Chariot webhook parse error: {e}")
            return {
                'event_type': 'error',
                'error': f'Invalid JSON: {e}'
            }

    def get_grants(
        self,
        tracking_id: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Query grants from Chariot.

        Args:
            tracking_id: Filter by tracking ID
            limit: Max results
            offset: Pagination offset
        """
        params = {
            'limit': limit,
            'offset': offset
        }

        if tracking_id:
            params['trackingId'] = tracking_id

        try:
            response = requests.get(
                f'{self._base_url}/grants',
                params=params,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'grants': data.get('grants', data if isinstance(data, list) else []),
                    'total': data.get('total', len(data) if isinstance(data, list) else 0)
                }
            else:
                data = response.json() if response.content else {}
                return {
                    'success': False,
                    'error': data.get('message', f'HTTP {response.status_code}')
                }

        except requests.RequestException as e:
            logger.error(f"Chariot get_grants error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        DAF grants cannot be refunded through Chariot.

        The grant goes to your nonprofit - refund would need to be
        processed as a separate donation back to the donor's DAF.
        """
        return {
            'success': False,
            'error': 'DAF grants cannot be refunded through the API. Contact donor directly.'
        }

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get grant details by ID.
        """
        try:
            response = requests.get(
                f'{self._base_url}/grants/{transaction_id}',
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
                    'error': f'Grant not found (HTTP {response.status_code})'
                }

        except requests.RequestException as e:
            logger.error(f"Chariot get_transaction error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def supports_currency(self, currency: str) -> bool:
        """DAFpay supports USD and potentially ILS."""
        return currency.upper() in ('USD', 'ILS')

    def supports_country(self, country_code: str) -> bool:
        """DAFpay supports US and Israel."""
        return country_code.upper() in ('US', 'IL')

    def supports_recurring(self) -> bool:
        """
        DAF grants are typically one-time.

        Recurring would be set up within the donor's DAF account.
        """
        return False

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """
        Estimate Chariot fee (2.9%).
        """
        return int(amount_cents * self.FEE_PERCENTAGE)
