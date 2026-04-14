"""
Base payment processor interface.
All credit card processors must implement this interface.
"""
from abc import ABC, abstractmethod


class BasePaymentProcessor(ABC):
    """Abstract base class for payment processors."""

    def __init__(self, config=None):
        self.config = config or {}

    @property
    @abstractmethod
    def code(self):
        """Unique processor code (e.g., 'shva', 'stripe', 'nedarim')."""
        pass

    @property
    @abstractmethod
    def name(self):
        """Human-readable processor name."""
        pass

    @property
    def display_name_he(self):
        """Hebrew display name."""
        return self.name

    @abstractmethod
    def create_payment(self, amount, currency, card_data, donor_data=None, **kwargs):
        """Create a payment/charge.
        Returns dict with: success, transaction_id, confirmation, error, raw_response
        """
        pass

    @abstractmethod
    def get_client_config(self):
        """Get frontend configuration (publishable keys, iframe URLs, etc.)."""
        pass

    def refund(self, transaction_id, amount=None):
        """Process a refund. Override in subclass if supported."""
        raise NotImplementedError(f"{self.name} does not support refunds")

    def check_card(self, card_number):
        """Validate a card number. Override if supported."""
        return {'valid': True}

    def get_transaction(self, transaction_id):
        """Get transaction details. Override if supported."""
        raise NotImplementedError

    def supports_currency(self, currency):
        """Check if processor supports a currency."""
        return currency.upper() in self.supported_currencies

    @property
    def supported_currencies(self):
        """List of supported currency codes."""
        return ['ILS', 'USD']

    @property
    def supported_countries(self):
        """List of supported country codes."""
        return ['IL']

    def estimate_fee(self, amount, currency):
        """Estimate processing fee."""
        return 0

    def test_connection(self):
        """Test API connectivity. Returns dict with success and message."""
        return {'success': True, 'message': 'Not implemented'}
