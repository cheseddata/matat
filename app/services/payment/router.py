"""
Payment routing logic.

Routes payments to the appropriate processor based on:
1. Database routing rules (priority ordered)
2. Currency/country constraints
3. User choice (when allowed)
"""
import logging
from typing import Dict, Any, List, Optional, Type

from .base import BasePaymentProcessor
from .stripe_processor import StripeProcessor
from .nedarim_processor import NedarimProcessor
from .cardcom_processor import CardComProcessor
from .grow_processor import GrowProcessor
from .tranzila_processor import TranzilaProcessor
from .payme_processor import PayMeProcessor
from .icount_processor import ICountProcessor
from .easycard_processor import EasyCardProcessor
from ...models.payment_processor import PaymentProcessor
from ...models.payment_routing_rule import PaymentRoutingRule

logger = logging.getLogger(__name__)


# Registry of processor implementations
PROCESSOR_CLASSES: Dict[str, Type[BasePaymentProcessor]] = {
    'stripe': StripeProcessor,
    'nedarim': NedarimProcessor,
    'cardcom': CardComProcessor,
    'grow': GrowProcessor,
    'tranzila': TranzilaProcessor,
    'payme': PayMeProcessor,
    'icount': ICountProcessor,
    'easycard': EasyCardProcessor,
}


def get_processor(code: str) -> Optional[BasePaymentProcessor]:
    """
    Get a processor instance by code.

    Args:
        code: Processor code ('stripe', 'nedarim')

    Returns:
        Initialized processor instance or None
    """
    # Get processor config from database
    db_processor = PaymentProcessor.get_by_code(code)
    if not db_processor or not db_processor.enabled:
        logger.warning(f'Processor {code} not found or not enabled')
        return None

    # Get the implementation class
    processor_class = PROCESSOR_CLASSES.get(code)
    if not processor_class:
        logger.error(f'No implementation for processor: {code}')
        return None

    # Create instance with config
    config = db_processor.config_json or {}
    processor = processor_class(config=config)

    if processor.initialize():
        return processor
    else:
        logger.error(f'Failed to initialize processor: {code}')
        return None


def get_processor_or_default(code: str) -> BasePaymentProcessor:
    """
    Get processor by code, falling back to Stripe.

    Always returns a working processor (Stripe as default).
    """
    processor = get_processor(code)
    if processor:
        return processor

    # Fall back to Stripe (always available)
    logger.info(f'Falling back to Stripe from {code}')
    stripe_processor = StripeProcessor()
    stripe_processor.initialize()
    return stripe_processor


class PaymentRouter:
    """
    Routes payments to appropriate processors based on rules.
    """

    def __init__(self):
        self._processors_cache: Dict[str, BasePaymentProcessor] = {}

    def route(
        self,
        amount_cents: int,
        currency: str,
        country_code: Optional[str] = None,
        donation_type: str = 'one_time',
        source: Optional[str] = None,
        campaign_id: Optional[int] = None,
        allow_user_choice: bool = True
    ) -> Dict[str, Any]:
        """
        Route a payment to the best processor.

        Args:
            amount_cents: Payment amount in smallest currency unit
            currency: Currency code (USD, ILS)
            country_code: Donor's country code (US, IL)
            donation_type: 'one_time' or 'recurring'
            source: Payment source ('web', 'phone', 'campaign')
            campaign_id: Campaign ID if applicable
            allow_user_choice: Whether to return alternatives for user selection

        Returns:
            Dict containing:
                - processor: Selected processor instance
                - reason: Why this processor was selected
                - alternatives: List of other available processors (if allow_user_choice)
                - rule_id: ID of matching rule (if any)
        """
        logger.info(f'Routing payment: {amount_cents} {currency}, country={country_code}, type={donation_type}')

        selected_processor = None
        reason = None
        rule_id = None

        # 1. Try to match a routing rule
        rules = PaymentRoutingRule.get_enabled_ordered()
        for rule in rules:
            if rule.matches(
                currency=currency,
                country_code=country_code,
                amount_cents=amount_cents,
                donation_type=donation_type,
                source=source,
                campaign_id=campaign_id
            ):
                processor = self._get_processor(rule.processor.code)
                if processor and processor.supports_currency(currency):
                    selected_processor = processor
                    reason = f'Matched rule: {rule.name}'
                    rule_id = rule.id
                    logger.info(f'Matched routing rule {rule.id}: {rule.name} -> {rule.processor.code}')
                    break

        # 2. If no rule matched, find best available processor
        if not selected_processor:
            selected_processor, reason = self._find_best_processor(
                currency=currency,
                country_code=country_code,
                amount_cents=amount_cents
            )

        # 3. Get alternatives if user choice allowed
        alternatives = []
        if allow_user_choice:
            alternatives = self._get_alternatives(
                selected_processor,
                currency=currency,
                country_code=country_code
            )

        return {
            'processor': selected_processor,
            'reason': reason,
            'rule_id': rule_id,
            'alternatives': alternatives,
        }

    def _get_processor(self, code: str) -> Optional[BasePaymentProcessor]:
        """Get processor from cache or create new."""
        if code not in self._processors_cache:
            processor = get_processor(code)
            if processor:
                self._processors_cache[code] = processor
        return self._processors_cache.get(code)

    def _find_best_processor(
        self,
        currency: str,
        country_code: Optional[str],
        amount_cents: int
    ) -> tuple:
        """
        Find the best processor when no rule matches.

        Uses heuristics:
        1. ILS currency -> prefer Nedarim if available
        2. Israel country -> prefer Nedarim if available
        3. Otherwise -> prefer Stripe (universal)
        4. Consider fees for large amounts
        """
        enabled_processors = PaymentProcessor.get_enabled()

        # Build list of viable processors
        viable = []
        for db_proc in enabled_processors:
            proc = self._get_processor(db_proc.code)
            if proc and proc.supports_currency(currency):
                viable.append((proc, db_proc))

        if not viable:
            # No viable processors, fall back to Stripe
            stripe = StripeProcessor()
            stripe.initialize()
            return stripe, 'Fallback: No enabled processors match criteria'

        # For ILS, prefer Nedarim
        if currency.upper() == 'ILS':
            for proc, db_proc in viable:
                if db_proc.code == 'nedarim':
                    return proc, 'Currency: ILS -> Nedarim preferred'

        # For Israel, prefer Nedarim
        if country_code and country_code.upper() == 'IL':
            for proc, db_proc in viable:
                if db_proc.code == 'nedarim':
                    return proc, 'Country: Israel -> Nedarim preferred'

        # For large amounts, consider fees
        if amount_cents >= 100000:  # $1000+
            # Sort by estimated fee
            viable.sort(key=lambda x: x[0].estimate_fee(amount_cents, currency))
            return viable[0][0], f'Large amount: lowest fee processor selected'

        # Default: use highest priority (lowest priority number)
        viable.sort(key=lambda x: x[1].priority)
        return viable[0][0], f'Default: {viable[0][1].code} (priority {viable[0][1].priority})'

    def _get_alternatives(
        self,
        selected: BasePaymentProcessor,
        currency: str,
        country_code: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get list of alternative processors for user choice."""
        alternatives = []
        enabled_processors = PaymentProcessor.get_enabled()

        for db_proc in enabled_processors:
            if db_proc.code == selected.code:
                continue  # Skip the selected one

            proc = self._get_processor(db_proc.code)
            if proc and proc.supports_currency(currency):
                alternatives.append({
                    'code': db_proc.code,
                    'name': db_proc.display_name or db_proc.name,
                    'display_order': db_proc.display_order,
                    'estimated_fee': proc.estimate_fee(100_00, currency),  # Fee for $100
                })

        # Sort by display order
        alternatives.sort(key=lambda x: x['display_order'])
        return alternatives


def route_payment(
    amount_cents: int,
    currency: str,
    country_code: Optional[str] = None,
    donation_type: str = 'one_time',
    source: Optional[str] = None,
    campaign_id: Optional[int] = None,
    allow_user_choice: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to route a payment.

    See PaymentRouter.route() for details.
    """
    router = PaymentRouter()
    return router.route(
        amount_cents=amount_cents,
        currency=currency,
        country_code=country_code,
        donation_type=donation_type,
        source=source,
        campaign_id=campaign_id,
        allow_user_choice=allow_user_choice
    )
