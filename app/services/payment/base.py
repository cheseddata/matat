"""
Abstract base class for payment processors.

All payment processors must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BasePaymentProcessor(ABC):
    """
    Abstract base class for payment processors.

    Each processor implementation (Stripe, Nedarim Plus, etc.) must inherit
    from this class and implement all abstract methods.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize processor with configuration.

        Args:
            config: Dictionary of processor-specific configuration
                   (API keys, mosad_id, etc.)
        """
        self.config = config or {}
        self._initialized = False

    @property
    @abstractmethod
    def code(self) -> str:
        """
        Unique processor identifier.

        Returns:
            Processor code string: 'stripe', 'nedarim', etc.
        """
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable processor name.

        Returns:
            Display name: 'Stripe', 'Nedarim Plus', etc.
        """
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the processor (API connections, credentials validation).

        Returns:
            True if initialization successful, False otherwise.
        """
        pass

    @abstractmethod
    def create_payment(
        self,
        amount_cents: int,
        currency: str,
        donor_email: str,
        donor_name: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a payment/payment intent.

        Args:
            amount_cents: Amount in smallest currency unit (cents/agorot)
            currency: Currency code (USD, ILS)
            donor_email: Donor's email address
            donor_name: Donor's full name
            metadata: Additional data to attach to payment

        Returns:
            Dict containing:
                - client_secret: For client-side payment confirmation (Stripe)
                - payment_id: Processor's payment/intent ID
                - additional processor-specific data for frontend
        """
        pass

    @abstractmethod
    def get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration needed by frontend to render payment UI.

        Returns:
            Dict containing:
                - type: 'elements' (Stripe) or 'iframe' (Nedarim)
                - publishable_key: For Stripe
                - iframe_url: For iframe-based processors
                - additional frontend config
        """
        pass

    @abstractmethod
    def process_webhook(self, request_data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Process and verify incoming webhook.

        Args:
            request_data: Raw request body
            headers: Request headers

        Returns:
            Dict containing normalized payment data:
                - event_type: 'payment_succeeded', 'payment_failed', etc.
                - transaction_id: Processor's transaction ID
                - amount_cents: Payment amount
                - currency: Currency code
                - donor_email: Donor email (if available)
                - donor_name: Donor name (if available)
                - raw_data: Original webhook payload
        """
        pass

    @abstractmethod
    def refund(
        self,
        transaction_id: str,
        amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process a refund.

        Args:
            transaction_id: Original transaction/payment ID
            amount_cents: Amount to refund (None = full refund)

        Returns:
            Dict containing:
                - success: True/False
                - refund_id: Processor's refund ID
                - amount_refunded: Amount actually refunded
                - error: Error message if failed
        """
        pass

    @abstractmethod
    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """
        Retrieve transaction details.

        Args:
            transaction_id: Processor's transaction ID

        Returns:
            Dict containing transaction details
        """
        pass

    def supports_currency(self, currency: str) -> bool:
        """
        Check if processor supports a currency.

        Override in subclass if needed.
        """
        return True

    def supports_country(self, country_code: str) -> bool:
        """
        Check if processor supports a country.

        Override in subclass if needed.
        """
        return True

    def supports_recurring(self) -> bool:
        """
        Check if processor supports recurring payments.

        Override in subclass if needed.
        """
        return True

    def charge_token(
        self,
        token: str,
        amount_cents: int,
        currency: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Charge a saved payment token (for recurring payments).

        Args:
            token: Saved payment token/buyer_key
            amount_cents: Amount to charge
            currency: Currency code
            metadata: Additional data

        Returns:
            Dict containing:
                - success: True/False
                - transaction_id: New transaction ID
                - error: Error message if failed
        """
        raise NotImplementedError(f"{self.code} does not support token charging")

    def save_token(
        self,
        donor_email: str,
        donor_name: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a token without charging (for future recurring).

        Args:
            donor_email: Donor's email
            donor_name: Donor's name
            metadata: Additional data

        Returns:
            Dict containing iframe/redirect data for tokenization
        """
        raise NotImplementedError(f"{self.code} does not support tokenization")

    def verify_webhook_origin(self, request_data: bytes, headers: Dict[str, str], remote_ip: str = None) -> bool:
        """
        Verify webhook origin is legitimate.

        Some processors use signature verification, others use IP whitelisting.

        Args:
            request_data: Raw request body
            headers: Request headers
            remote_ip: Remote IP address (for IP-based verification)

        Returns:
            True if origin is verified, False otherwise
        """
        return True  # Override in subclasses that need verification

    def get_recurring_status(self, recurring_id: str) -> Dict[str, Any]:
        """
        Get status of a recurring payment / standing order.

        Args:
            recurring_id: Recurring payment ID (subscription_id, keva_id, etc.)

        Returns:
            Dict containing recurring status details
        """
        raise NotImplementedError(f"{self.code} does not support recurring status check")

    def cancel_recurring(self, recurring_id: str) -> Dict[str, Any]:
        """
        Cancel a recurring payment / standing order.

        Args:
            recurring_id: Recurring payment ID

        Returns:
            Dict containing:
                - success: True/False
                - error: Error message if failed
        """
        raise NotImplementedError(f"{self.code} does not support recurring cancellation")

    def estimate_fee(self, amount_cents: int, currency: str) -> int:
        """
        Estimate processing fee for an amount.

        Override in subclass with actual fee calculation.

        Returns:
            Estimated fee in cents/agorot
        """
        return 0

    def __repr__(self):
        return f'<{self.__class__.__name__} [{self.code}]>'
